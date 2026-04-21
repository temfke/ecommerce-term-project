package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.AddressRequest;
import com.ecommerce.backend.dto.AddressResponse;
import com.ecommerce.backend.entity.Address;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.AddressRepository;
import com.ecommerce.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AddressService {

    private static final int MAX_ADDRESSES_PER_USER = 10;

    private final AddressRepository addressRepository;
    private final UserRepository userRepository;

    public List<AddressResponse> listForUser(User currentUser) {
        return addressRepository.findByUserId(currentUser.getId()).stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public AddressResponse create(AddressRequest request, User currentUser) {
        if (addressRepository.countByUserId(currentUser.getId()) >= MAX_ADDRESSES_PER_USER) {
            throw new BadRequestException("Maximum number of addresses reached");
        }
        User managed = userRepository.findById(currentUser.getId())
                .orElseThrow(() -> new BadRequestException("Authenticated user no longer exists"));

        boolean makeDefault = request.isDefault() || addressRepository.countByUserId(currentUser.getId()) == 0;

        Address address = Address.builder()
                .user(managed)
                .label(request.getLabel().trim())
                .line1(request.getLine1().trim())
                .line2(blankToNull(request.getLine2()))
                .city(request.getCity().trim())
                .state(blankToNull(request.getState()))
                .postalCode(request.getPostalCode().trim())
                .country(request.getCountry().trim())
                .isDefault(makeDefault)
                .build();

        Address saved = addressRepository.saveAndFlush(address);
        if (makeDefault) {
            addressRepository.clearDefaultExcept(currentUser.getId(), saved.getId());
        }
        return toResponse(saved);
    }

    @Transactional
    public AddressResponse update(Long id, AddressRequest request, User currentUser) {
        Address address = addressRepository.findByIdAndUserId(id, currentUser.getId())
                .orElseThrow(() -> new ResourceNotFoundException("Address not found"));

        address.setLabel(request.getLabel().trim());
        address.setLine1(request.getLine1().trim());
        address.setLine2(blankToNull(request.getLine2()));
        address.setCity(request.getCity().trim());
        address.setState(blankToNull(request.getState()));
        address.setPostalCode(request.getPostalCode().trim());
        address.setCountry(request.getCountry().trim());

        boolean makeDefault = request.isDefault();
        address.setDefault(makeDefault || address.isDefault());
        Address saved = addressRepository.save(address);
        if (saved.isDefault()) {
            addressRepository.clearDefaultExcept(currentUser.getId(), saved.getId());
        }
        return toResponse(saved);
    }

    @Transactional
    public AddressResponse setDefault(Long id, User currentUser) {
        Address address = addressRepository.findByIdAndUserId(id, currentUser.getId())
                .orElseThrow(() -> new ResourceNotFoundException("Address not found"));
        address.setDefault(true);
        Address saved = addressRepository.save(address);
        addressRepository.clearDefaultExcept(currentUser.getId(), saved.getId());
        return toResponse(saved);
    }

    @Transactional
    public void delete(Long id, User currentUser) {
        Address address = addressRepository.findByIdAndUserId(id, currentUser.getId())
                .orElseThrow(() -> new ResourceNotFoundException("Address not found"));
        boolean wasDefault = address.isDefault();
        addressRepository.delete(address);
        addressRepository.flush();
        if (wasDefault) {
            List<Address> remaining = addressRepository.findByUserId(currentUser.getId());
            if (!remaining.isEmpty()) {
                Address next = remaining.get(0);
                next.setDefault(true);
                addressRepository.save(next);
            }
        }
    }

    private String blankToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private AddressResponse toResponse(Address a) {
        return AddressResponse.builder()
                .id(a.getId())
                .label(a.getLabel())
                .line1(a.getLine1())
                .line2(a.getLine2())
                .city(a.getCity())
                .state(a.getState())
                .postalCode(a.getPostalCode())
                .country(a.getCountry())
                .isDefault(a.isDefault())
                .createdAt(a.getCreatedAt())
                .build();
    }
}
