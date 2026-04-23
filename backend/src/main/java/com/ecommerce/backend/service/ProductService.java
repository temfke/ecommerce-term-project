package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ProductRequest;
import com.ecommerce.backend.dto.ProductResponse;
import com.ecommerce.backend.entity.Category;
import com.ecommerce.backend.entity.Product;
import com.ecommerce.backend.entity.Store;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.exception.UnauthorizedException;
import com.ecommerce.backend.repository.CategoryRepository;
import com.ecommerce.backend.repository.ProductRepository;
import com.ecommerce.backend.repository.StoreRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductRepository productRepository;
    private final StoreRepository storeRepository;
    private final CategoryRepository categoryRepository;

    public List<ProductResponse> getAllActiveProducts() {
        return productRepository.findFirst100ByActiveTrueOrderByIdDesc().stream().map(this::toResponse).toList();
    }

    public List<ProductResponse> getProductsByStore(Long storeId) {
        return productRepository.findByStoreId(storeId).stream().map(this::toResponse).toList();
    }

    public List<ProductResponse> searchProducts(String query) {
        return productRepository.findFirst100ByNameContainingIgnoreCaseAndActiveTrueOrderByIdDesc(query)
                .stream().map(this::toResponse).toList();
    }

    private static final Set<String> ALLOWED_SORT_FIELDS =
            Set.of("name", "unitPrice", "stockQuantity", "createdAt", "id");

    public List<ProductResponse> filterAndSortProducts(
            String search, Long categoryId, Long storeId,
            String sortBy, String sortDir, int limit, int offset) {

        String safeSortBy = ALLOWED_SORT_FIELDS.contains(sortBy) ? sortBy : "id";
        Sort.Direction dir = "asc".equalsIgnoreCase(sortDir)
                ? Sort.Direction.ASC : Sort.Direction.DESC;
        int safeLimit = Math.min(Math.max(limit, 1), 500);
        int safeOffset = Math.max(offset, 0);
        int page = safeOffset / safeLimit;
        int leadingSkip = safeOffset % safeLimit;

        String safeSearch = (search != null && !search.isBlank()) ? search : null;

        if (leadingSkip == 0) {
            return productRepository.filterProducts(
                            safeSearch, categoryId, storeId,
                            PageRequest.of(page, safeLimit, Sort.by(dir, safeSortBy)))
                    .stream().map(this::toResponse).toList();
        }

        // Misaligned offset/limit: fetch a window starting at the requested offset.
        return productRepository.filterProducts(
                        safeSearch, categoryId, storeId,
                        PageRequest.of(0, safeOffset + safeLimit, Sort.by(dir, safeSortBy)))
                .stream().skip(safeOffset).limit(safeLimit).map(this::toResponse).toList();
    }

    public ProductResponse getProductById(Long id) {
        return toResponse(productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found")));
    }

    public ProductResponse createProduct(ProductRequest request, User currentUser) {
        Store store = storeRepository.findById(request.getStoreId())
                .orElseThrow(() -> new ResourceNotFoundException("Store not found"));

        if (!store.getOwner().getId().equals(currentUser.getId())
                && !currentUser.getRole().name().equals("ADMIN")) {
            throw new UnauthorizedException("Not authorized to add products to this store");
        }

        Product product = Product.builder()
                .name(request.getName())
                .description(request.getDescription())
                .sku(request.getSku())
                .unitPrice(request.getUnitPrice())
                .stockQuantity(request.getStockQuantity())
                .imageUrl(request.getImageUrl())
                .store(store)
                .build();

        if (request.getCategoryId() != null) {
            Category category = categoryRepository.findById(request.getCategoryId())
                    .orElseThrow(() -> new ResourceNotFoundException("Category not found"));
            product.setCategory(category);
        }

        return toResponse(productRepository.save(product));
    }

    public ProductResponse updateProduct(Long id, ProductRequest request, User currentUser) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found"));

        if (!product.getStore().getOwner().getId().equals(currentUser.getId())
                && !currentUser.getRole().name().equals("ADMIN")) {
            throw new UnauthorizedException("Not authorized to update this product");
        }

        if (request.getName() != null) product.setName(request.getName());
        if (request.getDescription() != null) product.setDescription(request.getDescription());
        if (request.getUnitPrice() != null) product.setUnitPrice(request.getUnitPrice());
        if (request.getStockQuantity() != null) product.setStockQuantity(request.getStockQuantity());
        if (request.getImageUrl() != null) product.setImageUrl(request.getImageUrl());
        if (request.getCategoryId() != null) {
            Category category = categoryRepository.findById(request.getCategoryId())
                    .orElseThrow(() -> new ResourceNotFoundException("Category not found"));
            product.setCategory(category);
        }

        return toResponse(productRepository.save(product));
    }

    public void deleteProduct(Long id, User currentUser) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found"));
        if (!product.getStore().getOwner().getId().equals(currentUser.getId())
                && !currentUser.getRole().name().equals("ADMIN")) {
            throw new UnauthorizedException("Not authorized to delete this product");
        }
        product.setActive(false);
        productRepository.save(product);
    }

    public List<ProductResponse> getLowStockProducts(Long storeId, int threshold) {
        return productRepository.findLowStockProducts(threshold).stream()
                .filter(p -> storeId == null || p.getStore().getId().equals(storeId))
                .map(this::toResponse)
                .toList();
    }

    private ProductResponse toResponse(Product product) {
        return ProductResponse.builder()
                .id(product.getId())
                .name(product.getName())
                .description(product.getDescription())
                .sku(product.getSku())
                .unitPrice(product.getUnitPrice())
                .stockQuantity(product.getStockQuantity())
                .imageUrl(product.getImageUrl())
                .active(product.isActive())
                .storeId(product.getStore().getId())
                .storeName(product.getStore().getName())
                .categoryId(product.getCategory() != null ? product.getCategory().getId() : null)
                .categoryName(product.getCategory() != null ? product.getCategory().getName() : null)
                .createdAt(product.getCreatedAt())
                .build();
    }
}
