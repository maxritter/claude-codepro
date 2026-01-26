---
name: Models Standards
description: Define database models with clear naming, appropriate data types, constraints, relationships, and validation at multiple layers. Use this skill when creating or modifying database model files, ORM classes, schema definitions, or data model relationships. Apply when working with model files (e.g., models.py, models/, ActiveRecord classes, Prisma schema, Sequelize models), defining table structures, setting up foreign keys and relationships, configuring cascade behaviors, implementing model validations, adding timestamps, or working with database constraints (NOT NULL, UNIQUE, foreign keys). Use for any task involving data integrity enforcement, relationship definitions, or model-level data validation.
---

# Models Standards

**Core Rule:** Models define data structure and integrity. Keep them focused on data representation, not business logic.

## When to use this skill

- When creating or modifying database model files (models.py, models/, schema.prisma, etc.)
- When defining ORM classes or ActiveRecord models for database tables
- When establishing table relationships (one-to-many, many-to-many, has-many, belongs-to)
- When configuring foreign keys, indexes, and cascade behaviors
- When implementing model-level validation rules
- When adding timestamp fields (created_at, updated_at) for auditing
- When setting database constraints (NOT NULL, UNIQUE, CHECK constraints)
- When choosing appropriate data types for model fields
- When balancing normalization with query performance needs
- When defining model methods or scopes for common queries

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle backend models.

## Naming Conventions

**Models:** Singular, PascalCase (`User`, `OrderItem`, `PaymentMethod`)

**Tables:** Plural, snake_case (`users`, `order_items`, `payment_methods`)

**Relationships:** Descriptive and clear
- `user.orders` (one-to-many)
- `order.items` (one-to-many)
- `product.categories` (many-to-many)

**Avoid generic names:** `data`, `info`, `record`, `entity`

## Required Fields

**Timestamps on every model:**
```python
created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Primary keys:** Always explicit, prefer UUIDs for distributed systems or auto-incrementing integers for simplicity

**Why:** Auditing, debugging, data lineage tracking, soft deletes

## Data Integrity - Database Level

**Use constraints, not just application validation:**

```python
# NOT NULL for required fields
email = Column(String(255), nullable=False)

# UNIQUE constraints
email = Column(String(255), unique=True, nullable=False)

# CHECK constraints for business rules
age = Column(Integer, CheckConstraint('age >= 18'))

# Foreign keys with explicit cascade behavior
user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
```

**Why:** Database enforces rules even if application code bypassed. Defense in depth.

## Data Types - Choose Appropriately

| Data       | Type               | Avoid       |
| ---------- | ------------------ | ----------- |
| Email, URL | VARCHAR(255)       | TEXT        |
| Short text | VARCHAR(n)         | TEXT        |
| Long text  | TEXT               | VARCHAR     |
| Money      | DECIMAL(10,2)      | FLOAT       |
| Boolean    | BOOLEAN            | TINYINT     |
| Timestamps | TIMESTAMP/DATETIME | VARCHAR     |
| JSON data  | JSON/JSONB         | TEXT        |
| UUIDs      | UUID               | VARCHAR(36) |

**Why:** Correct types enable database optimizations, constraints, and prevent data corruption.

## Indexes - Performance Critical

**Always index:**
- Primary keys (automatic)
- Foreign keys (manual in most ORMs)
- Columns in WHERE clauses
- Columns in JOIN conditions
- Columns in ORDER BY clauses

**Example:**
```python
class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    status = Column(String(50), index=True)  # Frequently filtered
    created_at = Column(DateTime, index=True)  # Frequently sorted
```

**Don't over-index:** Each index slows writes. Index only queried columns.

## Relationships - Explicit Configuration

**Define both sides of relationships:**

```python
# One-to-many
class User(Base):
    orders = relationship('Order', back_populates='user', cascade='all, delete-orphan')

class Order(Base):
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='orders')
```

**Cascade behaviors:**
- `CASCADE`: Delete related records (user deleted → orders deleted)
- `SET NULL`: Nullify foreign key (category deleted → product.category_id = NULL)
- `RESTRICT`: Prevent deletion if related records exist
- `NO ACTION`: Database default, usually same as RESTRICT

**Choose based on business logic, not convenience.**

## Validation - Two Layers

**Model-level validation (application):**
```python
@validates('email')
def validate_email(self, key, email):
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        raise ValueError('Invalid email format')
    return email
```

**Database-level constraints (see Data Integrity section)**

**Why both:** Model validation provides clear error messages. Database constraints prevent data corruption if application bypassed.

## What Belongs in Models

**YES:**
- Field definitions and types
- Relationships to other models
- Simple property methods (`@property def full_name`)
- Data validation rules
- Database constraints

**NO:**
- Business logic (move to service layer)
- External API calls
- Complex calculations (move to service methods)
- Email sending, file uploads, etc.

**Models represent data structure, not behavior.**

## Normalization vs Performance

**Normalize when:**
- Data has clear entity boundaries
- Updates need to propagate (user email changes once)
- Avoiding data duplication is critical

**Denormalize when:**
- Read performance critical (analytics, reporting)
- Data rarely changes (historical snapshots)
- Joins become too expensive

**Default to normalized. Denormalize only with evidence of performance issues.**

## Common Patterns

**Soft deletes:**
```python
deleted_at = Column(DateTime, nullable=True, index=True)

# Query only active records
query = session.query(User).filter(User.deleted_at.is_(None))
```

**Polymorphic associations:**
```python
# Avoid if possible - complex and hard to maintain
# Prefer separate relationship fields or inheritance
```

**Enums for fixed values:**
```python
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = 'pending'
    PAID = 'paid'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'

status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
```

## Testing Models

**Test constraints and validation:**
```python
def test_user_email_required():
    with pytest.raises(IntegrityError):
        user = User(name='Test')
        session.add(user)
        session.commit()

def test_user_email_unique():
    user1 = User(email='test@example.com')
    user2 = User(email='test@example.com')
    session.add(user1)
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(user2)
        session.commit()
```

**Test relationships:**
```python
def test_user_orders_cascade_delete():
    user = User(email='test@example.com')
    order = Order(user=user)
    session.add(user)
    session.commit()

    session.delete(user)
    session.commit()

    assert session.query(Order).count() == 0
```

## Checklist for New Models

- [ ] Singular model name, plural table name
- [ ] Primary key defined
- [ ] `created_at` and `updated_at` timestamps
- [ ] NOT NULL on required fields
- [ ] UNIQUE constraints where appropriate
- [ ] Foreign keys with explicit cascade behavior
- [ ] Indexes on foreign keys and queried columns
- [ ] Appropriate data types (not all VARCHAR)
- [ ] Validation at model and database levels
- [ ] Relationships defined on both sides
- [ ] Tests for constraints and validation
