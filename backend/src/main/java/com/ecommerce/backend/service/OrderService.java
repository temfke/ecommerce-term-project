package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.*;
import com.ecommerce.backend.entity.*;
import com.ecommerce.backend.enums.OrderStatus;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.exception.UnauthorizedException;
import com.ecommerce.backend.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
public class OrderService {

    private final OrderRepository orderRepository;
    private final ProductRepository productRepository;
    private final StoreRepository storeRepository;
    private final CustomerProfileRepository customerProfileRepository;

    @Transactional
    public OrderResponse createOrder(OrderRequest request, User currentUser) {
        Store store = storeRepository.findById(request.getStoreId())
                .orElseThrow(() -> new ResourceNotFoundException("Store not found"));

        Order order = Order.builder()
                .user(currentUser)
                .store(store)
                .status(OrderStatus.PENDING)
                .paymentMethod(request.getPaymentMethod())
                .shippingAddress(request.getShippingAddress())
                .grandTotal(BigDecimal.ZERO)
                .build();

        BigDecimal total = BigDecimal.ZERO;

        for (OrderItemRequest itemReq : request.getItems()) {
            Product product = productRepository.findById(itemReq.getProductId())
                    .orElseThrow(() -> new ResourceNotFoundException("Product not found"));

            if (product.getStockQuantity() < itemReq.getQuantity()) {
                throw new BadRequestException("Insufficient stock for product: " + product.getName());
            }

            product.setStockQuantity(product.getStockQuantity() - itemReq.getQuantity());
            productRepository.save(product);

            BigDecimal itemTotal = product.getUnitPrice().multiply(BigDecimal.valueOf(itemReq.getQuantity()));
            total = total.add(itemTotal);

            OrderItem orderItem = OrderItem.builder()
                    .order(order)
                    .product(product)
                    .quantity(itemReq.getQuantity())
                    .price(product.getUnitPrice())
                    .build();
            order.getItems().add(orderItem);
        }

        order.setGrandTotal(total);
        order = orderRepository.save(order);

        final BigDecimal finalTotal = total;
        int itemCount = request.getItems().size();
        customerProfileRepository.findByUserId(currentUser.getId()).ifPresent(profile -> {
            profile.setTotalSpend(profile.getTotalSpend().add(finalTotal));
            profile.setItemsPurchased(profile.getItemsPurchased() + itemCount);
            customerProfileRepository.save(profile);
        });

        return toResponse(order);
    }

    public List<OrderResponse> getOrdersByUser(Long userId) {
        return orderRepository.findByUserId(userId).stream().map(this::toResponse).toList();
    }

    public List<OrderResponse> getOrdersByStore(Long storeId) {
        return orderRepository.findByStoreId(storeId).stream().map(this::toResponse).toList();
    }

    public List<OrderResponse> getAllOrders() {
        return orderRepository.findAllOrderedByCreatedAt().stream().map(this::toResponse).toList();
    }

    public List<OrderResponse> getOrdersForStoreOwner(Long ownerId) {
        return orderRepository.findByStoreOwnerId(ownerId).stream().map(this::toResponse).toList();
    }

    public List<OrderResponse> getOrdersForCurrentUser(User currentUser) {
        return switch (currentUser.getRole()) {
            case ADMIN -> getAllOrders();
            case CORPORATE -> getOrdersForStoreOwner(currentUser.getId());
            default -> getOrdersByUser(currentUser.getId());
        };
    }

    public OrderResponse getOrderById(Long id, User currentUser) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        boolean isOwner = order.getUser().getId().equals(currentUser.getId());
        boolean isStoreOwner = order.getStore().getOwner().getId().equals(currentUser.getId());
        boolean isAdmin = currentUser.getRole().name().equals("ADMIN");

        if (!isOwner && !isStoreOwner && !isAdmin) {
            throw new UnauthorizedException("Not authorized to view this order");
        }

        return toResponse(order);
    }

    @Transactional
    public OrderResponse updateOrderStatus(Long id, OrderStatus status, User currentUser) {
        Order order = orderRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        boolean isStoreOwner = order.getStore().getOwner().getId().equals(currentUser.getId());
        boolean isAdmin = currentUser.getRole().name().equals("ADMIN");

        if (!isStoreOwner && !isAdmin) {
            throw new UnauthorizedException("Not authorized to update this order");
        }

        if (status == OrderStatus.CANCELLED && order.getStatus() != OrderStatus.CANCELLED) {
            for (OrderItem item : order.getItems()) {
                Product product = item.getProduct();
                product.setStockQuantity(product.getStockQuantity() + item.getQuantity());
                productRepository.save(product);
            }
        }

        order.setStatus(status);
        return toResponse(orderRepository.save(order));
    }

    private OrderResponse toResponse(Order order) {
        List<OrderItemResponse> items = order.getItems().stream()
                .map(item -> OrderItemResponse.builder()
                        .id(item.getId())
                        .productId(item.getProduct().getId())
                        .productName(item.getProduct().getName())
                        .quantity(item.getQuantity())
                        .price(item.getPrice())
                        .build())
                .toList();

        return OrderResponse.builder()
                .id(order.getId())
                .userId(order.getUser().getId())
                .customerName(order.getUser().getFirstName() + " " + order.getUser().getLastName())
                .customerEmail(order.getUser().getEmail())
                .storeId(order.getStore().getId())
                .storeName(order.getStore().getName())
                .status(order.getStatus())
                .grandTotal(order.getGrandTotal())
                .paymentMethod(order.getPaymentMethod())
                .shippingAddress(order.getShippingAddress())
                .items(items)
                .createdAt(order.getCreatedAt())
                .build();
    }
}
