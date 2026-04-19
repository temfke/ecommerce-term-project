package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.StoreRequest;
import com.ecommerce.backend.dto.StoreResponse;
import com.ecommerce.backend.entity.Store;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.StoreStatus;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.exception.UnauthorizedException;
import com.ecommerce.backend.repository.StoreRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class StoreService {

    private final StoreRepository storeRepository;

    public List<StoreResponse> getAllStores() {
        return storeRepository.findAll().stream().map(this::toResponse).toList();
    }

    public List<StoreResponse> getStoresByOwner(Long ownerId) {
        return storeRepository.findByOwnerId(ownerId).stream().map(this::toResponse).toList();
    }

    public StoreResponse getStoreById(Long id) {
        return toResponse(storeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Store not found")));
    }

    public StoreResponse createStore(StoreRequest request, User owner) {
        Store store = Store.builder()
                .name(request.getName())
                .description(request.getDescription())
                .logoUrl(request.getLogoUrl())
                .owner(owner)
                .status(StoreStatus.PENDING_APPROVAL)
                .build();
        return toResponse(storeRepository.save(store));
    }

    public StoreResponse updateStore(Long id, StoreRequest request, User currentUser) {
        Store store = storeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Store not found"));
        if (!store.getOwner().getId().equals(currentUser.getId())
                && !currentUser.getRole().name().equals("ADMIN")) {
            throw new UnauthorizedException("Not authorized to update this store");
        }
        if (request.getName() != null) store.setName(request.getName());
        if (request.getDescription() != null) store.setDescription(request.getDescription());
        if (request.getLogoUrl() != null) store.setLogoUrl(request.getLogoUrl());
        return toResponse(storeRepository.save(store));
    }

    public StoreResponse updateStoreStatus(Long id, StoreStatus status) {
        Store store = storeRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Store not found"));
        store.setStatus(status);
        return toResponse(storeRepository.save(store));
    }

    private StoreResponse toResponse(Store store) {
        return StoreResponse.builder()
                .id(store.getId())
                .name(store.getName())
                .description(store.getDescription())
                .logoUrl(store.getLogoUrl())
                .status(store.getStatus())
                .ownerId(store.getOwner().getId())
                .ownerName(store.getOwner().getFirstName() + " " + store.getOwner().getLastName())
                .createdAt(store.getCreatedAt())
                .build();
    }
}
