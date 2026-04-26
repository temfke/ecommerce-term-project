package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.ChatAudit;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ChatAuditRepository extends JpaRepository<ChatAudit, Long> {

    @Query("SELECT a FROM ChatAudit a ORDER BY a.createdAt DESC")
    List<ChatAudit> findAllPaged(Pageable pageable);

    @Query("SELECT a FROM ChatAudit a WHERE a.status = :status ORDER BY a.createdAt DESC")
    List<ChatAudit> findByStatusPaged(@Param("status") String status, Pageable pageable);

    @Query("SELECT a FROM ChatAudit a WHERE a.userId = :userId ORDER BY a.createdAt DESC")
    List<ChatAudit> findByUserIdPaged(@Param("userId") Long userId, Pageable pageable);
}
