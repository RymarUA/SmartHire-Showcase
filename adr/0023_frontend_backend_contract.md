# ADR 0023: Frontend-Backend Contract

**Status:** Accepted
**Date:** 2026-04-20
**Author:** SmartHire Architecture Team

## Context

The SmartHire platform consists of multiple frontend applications (Dashboard, TG Mini App, Onboarding) communicating with a shared FastAPI backend. Without a clear contract, frontend-backend integration becomes fragile and error-prone.

## Decision

Establish a strict contract between frontend and backend:

### 1. API-First Design

- All data exchange through RESTful APIs
- OpenAPI/Swagger documentation mandatory
- Versioned API endpoints (`/api/v1/...`)

### 2. Type Safety

- Pydantic models on backend → TypeScript interfaces on frontend
- Shared types via packages (e.g., `@smarthire/api-client`)
- Strict serialization rules (no custom JSON hacks)

### 3. Error Handling Contract

```typescript
// Backend returns:
interface ApiError {
  detail: string;
  code?: string;
  validation_errors?: Array<{
    field: string;
    message: string;
  }>;
}

// Frontend handles:
function handleError(error: ApiError) {
  if (error.code === 'TENANT_NOT_FOUND') {
    // Redirect to onboarding
  }
}
```

### 4. Pagination Standard

```typescript
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}
```

### 5. Authentication Flow

- JWT in httpOnly cookies (not localStorage)
- Refresh token rotation
- Tenant context in headers (`X-Tenant-ID`)

## Consequences

### Positive

- Clear integration boundaries
- Type-safe frontend development
- Predictable error handling
- Easy to mock for testing
- OpenAPI docs for API discovery

### Negative

- Initial setup overhead
- Need to maintain type同步
- Cannot make "quick" endpoint changes

## Implementation

| Component | Status |
|-----------|--------|
| OpenAPI generation | ✅ |
| Shared API client package | ✅ |
| TypeScript interfaces | ✅ |
| Error boundary components | ✅ |
| Pagination hooks | ✅ |

## References

- API Client: `packages/api-client/`
- Dashboard: `dashboard/`
- TG Mini App: `tg_miniapp/`
