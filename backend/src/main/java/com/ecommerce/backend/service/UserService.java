package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.UserResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.Role;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;

    public List<UserResponse> getAllUsers() {
        return userRepository.findAll().stream().map(this::toResponse).toList();
    }

    public List<UserResponse> getUsersByRole(Role role) {
        return userRepository.findByRole(role).stream().map(this::toResponse).toList();
    }

    public UserResponse getUserById(Long id) {
        return toResponse(userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User not found")));
    }

    public UserResponse toggleUserStatus(Long id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User not found"));
        user.setEnabled(!user.isEnabled());
        return toResponse(userRepository.save(user));
    }

    public void deleteUser(Long id) {
        if (!userRepository.existsById(id)) {
            throw new ResourceNotFoundException("User not found");
        }
        userRepository.deleteById(id);
    }

    private UserResponse toResponse(User user) {
        return UserResponse.builder()
                .id(user.getId())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .role(user.getRole())
                .gender(user.getGender())
                .phone(user.getPhone())
                .enabled(user.isEnabled())
                .emailVerified(user.isEmailVerified())
                .createdAt(user.getCreatedAt())
                .build();
    }
}
