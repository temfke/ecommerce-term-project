package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.CheckoutSessionRequest;
import com.ecommerce.backend.dto.CheckoutSessionResponse;
import com.ecommerce.backend.dto.OrderItemRequest;
import com.ecommerce.backend.dto.OrderRequest;
import com.ecommerce.backend.dto.OrderResponse;
import com.ecommerce.backend.dto.PaymentConfirmResponse;
import com.ecommerce.backend.entity.Product;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.PaymentMethod;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.OrderRepository;
import com.ecommerce.backend.repository.ProductRepository;
import com.stripe.exception.StripeException;
import com.stripe.model.checkout.Session;
import com.stripe.param.checkout.SessionCreateParams;
import com.stripe.param.checkout.SessionUpdateParams;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);
    private static final String CURRENCY = "usd";

    private final ProductRepository productRepository;
    private final OrderRepository orderRepository;
    private final OrderService orderService;

    @Value("${stripe.success-url}")
    private String successUrl;

    @Value("${stripe.cancel-url}")
    private String cancelUrl;

    public CheckoutSessionResponse createCheckoutSession(CheckoutSessionRequest request, User currentUser) {
        if (currentUser == null || currentUser.getId() == null) {
            throw new BadRequestException("Authentication required to start checkout");
        }
        if (request.getItems() == null || request.getItems().isEmpty()) {
            throw new BadRequestException("Cart is empty");
        }

        List<SessionCreateParams.LineItem> lineItems = new ArrayList<>();
        StringBuilder cartMeta = new StringBuilder();
        for (OrderItemRequest item : request.getItems()) {
            Product product = productRepository.findById(item.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException("Product not found: " + item.getProductId()));
            if (product.getStockQuantity() < item.getQuantity()) {
                throw new BadRequestException("Insufficient stock for product: " + product.getName());
            }

            BigDecimal price = product.getUnitPrice() == null ? BigDecimal.ZERO : product.getUnitPrice();
            long unitAmountCents = price.multiply(BigDecimal.valueOf(100)).longValueExact();
            if (unitAmountCents < 50) {
                throw new BadRequestException("Item price below Stripe minimum: " + product.getName());
            }

            lineItems.add(SessionCreateParams.LineItem.builder()
                    .setQuantity((long) item.getQuantity())
                    .setPriceData(SessionCreateParams.LineItem.PriceData.builder()
                            .setCurrency(CURRENCY)
                            .setUnitAmount(unitAmountCents)
                            .setProductData(SessionCreateParams.LineItem.PriceData.ProductData.builder()
                                    .setName(product.getName())
                                    .build())
                            .build())
                    .build());

            if (cartMeta.length() > 0) cartMeta.append(",");
            cartMeta.append(product.getId()).append(":").append(item.getQuantity());
        }

        if (cartMeta.length() > 480) {
            throw new BadRequestException("Cart too large for Stripe checkout (max ~30 distinct items)");
        }

        SessionCreateParams.Builder paramsBuilder = SessionCreateParams.builder()
                .setMode(SessionCreateParams.Mode.PAYMENT)
                .setSuccessUrl(successUrl)
                .setCancelUrl(cancelUrl)
                .setCustomerEmail(currentUser.getEmail())
                .putMetadata("userId", String.valueOf(currentUser.getId()))
                .putMetadata("storeId", String.valueOf(request.getStoreId()))
                .putMetadata("cart", cartMeta.toString());

        if (request.getShippingAddress() != null && !request.getShippingAddress().isBlank()) {
            String addr = request.getShippingAddress().length() > 480
                    ? request.getShippingAddress().substring(0, 480)
                    : request.getShippingAddress();
            paramsBuilder.putMetadata("shippingAddress", addr);
        }

        for (SessionCreateParams.LineItem li : lineItems) {
            paramsBuilder.addLineItem(li);
        }

        try {
            Session session = Session.create(paramsBuilder.build());
            return CheckoutSessionResponse.builder()
                    .sessionId(session.getId())
                    .url(session.getUrl())
                    .build();
        } catch (StripeException ex) {
            log.error("Stripe session creation failed", ex);
            throw new BadRequestException("Could not start payment: " + ex.getMessage());
        }
    }

    public PaymentConfirmResponse confirm(String sessionId, User currentUser) {
        if (currentUser == null || currentUser.getId() == null) {
            throw new BadRequestException("Authentication required");
        }
        if (sessionId == null || sessionId.isBlank()) {
            throw new BadRequestException("Session id is required");
        }

        Session session;
        try {
            session = Session.retrieve(sessionId);
        } catch (StripeException ex) {
            log.error("Stripe session retrieval failed", ex);
            throw new BadRequestException("Could not retrieve payment session");
        }

        String userIdMeta = session.getMetadata().get("userId");
        if (userIdMeta == null || !userIdMeta.equals(String.valueOf(currentUser.getId()))) {
            throw new BadRequestException("Session does not belong to current user");
        }

        String paymentStatus = session.getPaymentStatus();
        if (!"paid".equalsIgnoreCase(paymentStatus)) {
            return PaymentConfirmResponse.builder().status(paymentStatus == null ? "unpaid" : paymentStatus).build();
        }

        String existingOrderId = session.getMetadata().get("orderId");
        if (existingOrderId != null) {
            return orderRepository.findById(Long.valueOf(existingOrderId))
                    .map(o -> PaymentConfirmResponse.builder()
                            .status("paid")
                            .order(orderService.getOrderById(o.getId(), currentUser))
                            .build())
                    .orElseGet(() -> PaymentConfirmResponse.builder().status("paid").build());
        }

        OrderRequest orderRequest = new OrderRequest();
        orderRequest.setStoreId(Long.valueOf(session.getMetadata().get("storeId")));
        orderRequest.setPaymentMethod(PaymentMethod.CREDIT_CARD);
        orderRequest.setShippingAddress(session.getMetadata().getOrDefault("shippingAddress", ""));
        orderRequest.setItems(parseCart(session.getMetadata().get("cart")));

        OrderResponse created = orderService.createOrder(orderRequest, currentUser);

        try {
            session.update(SessionUpdateParams.builder()
                    .putMetadata("orderId", String.valueOf(created.getId()))
                    .build());
        } catch (StripeException ex) {
            log.warn("Could not stamp orderId onto Stripe session {}: {}", sessionId, ex.getMessage());
        }

        return PaymentConfirmResponse.builder().status("paid").order(created).build();
    }

    private List<OrderItemRequest> parseCart(String cartMeta) {
        List<OrderItemRequest> items = new ArrayList<>();
        if (cartMeta == null || cartMeta.isBlank()) return items;
        for (String pair : cartMeta.split(",")) {
            String[] parts = pair.split(":");
            if (parts.length != 2) continue;
            OrderItemRequest item = new OrderItemRequest();
            item.setProductId(Long.valueOf(parts[0].trim()));
            item.setQuantity(Integer.parseInt(parts[1].trim()));
            items.add(item);
        }
        return items;
    }
}
