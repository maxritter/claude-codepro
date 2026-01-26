---
name: API Standards
description: Design and implement RESTful API endpoints following REST principles with proper HTTP methods, status codes, and resource-based URLs. Use this skill when creating or modifying API endpoints, route handlers, controllers, or API configuration files. Apply when working on REST API design, endpoint implementations, API versioning, request/response handling, HTTP method routing (GET, POST, PUT, PATCH, DELETE), query parameter filtering, API rate limiting, or any file that defines API routes such as routes.py, api.js, controllers/, endpoints/, or API documentation files.
---

# API Standards

Apply these standards when creating or modifying API endpoints, route handlers, and controllers.

## When to use this skill

- When creating or modifying API endpoint files (routes.py, api.js, controllers/, endpoints/, etc.)
- When implementing REST API route handlers and controllers
- When designing resource-based URL structures and HTTP method routing
- When working with API versioning strategies in URL paths or headers
- When implementing query parameters for filtering, sorting, pagination, or search
- When configuring HTTP status codes for API responses
- When setting up rate limiting headers or API middleware
- When writing API documentation or OpenAPI/Swagger specifications
- When refactoring existing API endpoints for consistency or REST compliance

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle backend API.

## RESTful Design Principles

**Resource-based URLs with HTTP methods:**
- `GET /users` - List users
- `GET /users/{id}` - Get specific user
- `POST /users` - Create user
- `PUT /users/{id}` - Replace user (full update)
- `PATCH /users/{id}` - Update user (partial update)
- `DELETE /users/{id}` - Delete user

**Use plural nouns for collections:**
- ✅ `/users`, `/products`, `/orders`
- ❌ `/user`, `/product`, `/order`

**Limit nesting to 2-3 levels:**
- ✅ `/users/{id}/orders`
- ✅ `/users/{id}/orders/{order_id}`
- ❌ `/users/{id}/orders/{order_id}/items/{item_id}/reviews`

## URL and Naming Conventions

**Consistent casing:**
- Use lowercase with hyphens: `/user-profiles` or underscores: `/user_profiles`
- Never mix: ❌ `/userProfiles`, ❌ `/User-Profiles`
- Check existing endpoints first and match the project's convention

**Query parameters for operations:**
- Filtering: `GET /users?status=active&role=admin`
- Sorting: `GET /users?sort=created_at&order=desc`
- Pagination: `GET /users?page=2&limit=50` or `?offset=100&limit=50`
- Search: `GET /users?q=john`

**Avoid creating separate endpoints for these operations.**

## HTTP Status Codes

Return accurate status codes:

**Success:**
- `200 OK` - Successful GET, PUT, PATCH, DELETE
- `201 Created` - Successful POST (include `Location` header)
- `204 No Content` - Successful DELETE with no response body

**Client Errors:**
- `400 Bad Request` - Invalid input, validation failure
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Duplicate resource, constraint violation
- `422 Unprocessable Entity` - Semantic validation failure

**Server Errors:**
- `500 Internal Server Error` - Unexpected server error
- `503 Service Unavailable` - Temporary unavailability

## API Versioning

**Choose one strategy and apply consistently:**

URL path versioning (recommended for simplicity):
```
/v1/users
/v2/users
```

Header versioning (for cleaner URLs):
```
Accept: application/vnd.api.v1+json
```

**When to version:**
- Breaking changes to request/response format
- Removing fields or endpoints
- Changing field types or validation rules

**Don't version for:**
- Adding optional fields
- Adding new endpoints
- Bug fixes

## Request/Response Patterns

**Consistent response structure:**
```json
{
  "data": { "id": 1, "name": "John" },
  "meta": { "timestamp": "2024-01-01T00:00:00Z" }
}
```

**Error response structure:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  }
}
```

**Pagination metadata:**
```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "limit": 50,
    "total": 250,
    "pages": 5
  }
}
```

## Rate Limiting

**Include rate limit headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

Return `429 Too Many Requests` when limit exceeded.

## Validation and Error Handling

**Validate at API boundary:**
- Check required fields before processing
- Validate formats (email, phone, URL)
- Enforce business rules
- Return specific error messages

**Never expose internal errors to clients:**
- ❌ Database error messages
- ❌ Stack traces
- ❌ Internal file paths
- ✅ Generic "Internal server error" with request ID for tracking

## Documentation

**Document each endpoint:**
- Purpose and use case
- Request parameters and body schema
- Response schema and status codes
- Authentication requirements
- Rate limits
- Example requests/responses

Use OpenAPI/Swagger for machine-readable documentation.

## Before Completing API Work

- [ ] Endpoints follow REST principles
- [ ] URLs use consistent naming convention
- [ ] HTTP methods match operations (GET for read, POST for create, etc.)
- [ ] Status codes accurately reflect responses
- [ ] Validation happens at API boundary
- [ ] Error responses are structured and specific
- [ ] Rate limiting headers included (if applicable)
- [ ] Documentation updated
- [ ] Tests cover success and error cases
