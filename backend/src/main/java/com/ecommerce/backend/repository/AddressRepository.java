package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Address;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface AddressRepository extends JpaRepository<Address, Long> {

    @Query("SELECT a FROM Address a WHERE a.user.id = :userId ORDER BY a.isDefault DESC, a.createdAt DESC")
    List<Address> findByUserId(@Param("userId") Long userId);

    @Query("SELECT a FROM Address a WHERE a.id = :id AND a.user.id = :userId")
    Optional<Address> findByIdAndUserId(@Param("id") Long id, @Param("userId") Long userId);

    @Modifying
    @Query("UPDATE Address a SET a.isDefault = false WHERE a.user.id = :userId AND a.id <> :keepId")
    void clearDefaultExcept(@Param("userId") Long userId, @Param("keepId") Long keepId);

    @Modifying
    @Query("UPDATE Address a SET a.isDefault = false WHERE a.user.id = :userId")
    void clearAllDefaults(@Param("userId") Long userId);

    @Query("SELECT COUNT(a) FROM Address a WHERE a.user.id = :userId")
    long countByUserId(@Param("userId") Long userId);
}
