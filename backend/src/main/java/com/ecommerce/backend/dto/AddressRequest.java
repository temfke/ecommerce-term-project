package com.ecommerce.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class AddressRequest {

    @NotBlank
    @Size(max = 60)
    private String label;

    @NotBlank
    @Size(max = 200)
    private String line1;

    @Size(max = 200)
    private String line2;

    @NotBlank
    @Size(max = 100)
    private String city;

    @Size(max = 100)
    private String state;

    @NotBlank
    @Size(max = 30)
    private String postalCode;

    @NotBlank
    @Size(max = 100)
    private String country;

    private boolean isDefault;
}
