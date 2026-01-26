---
name: Migration Standards
description: Create and manage database migrations with reversible changes, proper naming conventions, and zero-downtime deployment strategies. Use this skill when creating database migration files, modifying schema, adding or removing tables/columns, managing indexes, or handling data migrations. Apply when working with migration files (e.g., db/migrate/, migrations/, alembic/, sequelize migrations), schema changes, database versioning, rollback implementations, or when you need to ensure backwards compatibility during deployments. Use for any task involving database structure changes, index creation, constraint modifications, or data transformation scripts.
---

# Migration Standards

Apply these rules when creating or modifying database migrations. Migrations are permanent records of schema evolution and must be treated with extreme care.

## When to use this skill

- When creating new database migration files (db/migrate/, migrations/, alembic/, etc.)
- When modifying database schema such as adding, removing, or altering tables and columns
- When implementing rollback/down methods for reversible migrations
- When creating indexes on database tables, especially large tables requiring concurrent indexing
- When writing data migrations to transform or populate data
- When planning zero-downtime deployments that require backwards-compatible schema changes
- When establishing naming conventions for migration files
- When separating schema changes from data migrations
- When reviewing or modifying existing migrations for safety and clarity

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle backend migrations.

## Core Principles

**Reversibility is Mandatory**: Every migration MUST have a working rollback method. Test the down migration immediately after writing the up migration. If a change cannot be reversed safely (e.g., dropping a column with data), document why in comments and consider a multi-step approach.

**One Logical Change Per Migration**: Each migration should do exactly one thing - add a table, add a column, create an index, etc. This makes debugging easier, rollbacks safer, and code review clearer. If you need to make multiple related changes, create multiple migrations.

**Never Modify Deployed Migrations**: Once a migration runs in any shared environment (staging, production), it becomes immutable. Create a new migration to fix issues. Modifying deployed migrations breaks version control and causes deployment failures.

## Migration Structure

**Naming Convention**: Use timestamps and descriptive names that indicate the change:
- `20241118120000_add_email_to_users.py`
- `20241118120100_create_orders_table.rb`
- `20241118120200_add_index_on_users_email.js`

The name should answer "what does this migration do?" without reading the code.

**File Organization**:
- Schema changes: `migrations/schema/`
- Data migrations: `migrations/data/`
- Keep them separate for rollback safety and clarity

## Schema Changes

**Adding Columns**: Always specify default values for NOT NULL columns on existing tables to avoid locking issues:

```python
# BAD - locks table during backfill
op.add_column('users', sa.Column('status', sa.String(), nullable=False))

# GOOD - uses default, no lock
op.add_column('users', sa.Column('status', sa.String(), nullable=False, server_default='active'))
```

**Removing Columns**: Use multi-step approach for zero-downtime:
1. Deploy code that stops using the column
2. Deploy migration that removes the column
3. Never combine these steps

**Renaming Columns**: Treat as add + remove for zero-downtime:
1. Add new column
2. Deploy code that writes to both columns
3. Backfill data
4. Deploy code that reads from new column
5. Remove old column

## Index Management

**Creating Indexes**: Use concurrent index creation on large tables to avoid blocking writes:

```python
# PostgreSQL
op.create_index('idx_users_email', 'users', ['email'], postgresql_using='btree', postgresql_concurrently=True)

# MySQL
op.create_index('idx_users_email', 'users', ['email'], mysql_algorithm='INPLACE', mysql_lock='NONE')
```

**Index Naming**: Use pattern `idx_<table>_<column(s)>` for clarity:
- `idx_users_email`
- `idx_orders_user_id_created_at`

**When to Index**: Add indexes for:
- Foreign key columns (always)
- Columns in WHERE clauses
- Columns in ORDER BY clauses
- Columns in JOIN conditions

## Data Migrations

**Separate from Schema**: Never mix schema and data changes in one migration. Schema changes are structural and fast; data changes are operational and slow.

**Batch Processing**: Process large datasets in batches to avoid memory issues and long-running transactions:

```python
def upgrade():
    batch_size = 1000
    connection = op.get_bind()

    while True:
        result = connection.execute(
            "UPDATE users SET status = 'active' WHERE status IS NULL LIMIT %s",
            batch_size
        )
        if result.rowcount == 0:
            break
```

**Idempotency**: Data migrations should be safe to run multiple times:

```python
# BAD - fails on second run
op.execute("INSERT INTO settings (key, value) VALUES ('feature_flag', 'true')")

# GOOD - idempotent
op.execute("INSERT INTO settings (key, value) VALUES ('feature_flag', 'true') ON CONFLICT (key) DO NOTHING")
```

## Zero-Downtime Deployments

**Backwards Compatibility**: New migrations must work with the currently deployed code version. Deploy order:
1. Deploy migration (schema change)
2. Deploy new code (uses new schema)

**Additive Changes First**: When changing column types or constraints:
1. Add new column/table
2. Deploy code that writes to both
3. Backfill data
4. Deploy code that reads from new location
5. Remove old column/table

**Foreign Key Constraints**: Add in separate migration after data is consistent to avoid validation failures.

## Testing Migrations

**Before Committing**:
1. Run migration up: `rake db:migrate` or equivalent
2. Verify schema changes: Check database structure
3. Run migration down: `rake db:rollback` or equivalent
4. Verify rollback worked: Check schema restored
5. Run migration up again: Ensure it's repeatable

**Test with Production-Like Data**: Use anonymized production data dump to test migrations against realistic data volumes and edge cases.

## Common Patterns by Framework

**Alembic (Python)**:
```python
def upgrade():
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.create_index('idx_users_email', 'users', ['email'])

def downgrade():
    op.drop_index('idx_users_email', 'users')
    op.drop_column('users', 'email')
```

**Rails (Ruby)**:
```ruby
def change
  add_column :users, :email, :string
  add_index :users, :email
end
```

**Sequelize (JavaScript)**:
```javascript
module.exports = {
  up: async (queryInterface, Sequelize) => {
    await queryInterface.addColumn('users', 'email', {
      type: Sequelize.STRING,
      allowNull: true
    });
    await queryInterface.addIndex('users', ['email']);
  },
  down: async (queryInterface, Sequelize) => {
    await queryInterface.removeIndex('users', ['email']);
    await queryInterface.removeColumn('users', 'email');
  }
};
```

## Red Flags - Stop and Reconsider

If you're about to:
- Modify an existing migration file that's been deployed
- Drop a column without a multi-step plan
- Create a migration without a down method
- Mix schema and data changes in one migration
- Add a NOT NULL column without a default to a large table
- Create an index without CONCURRENT on a production table

**STOP. Review this document and plan a safer approach.**

## Checklist Before Committing

- [ ] Migration has descriptive timestamp-based name
- [ ] Down/rollback method implemented and tested
- [ ] Ran migration up successfully
- [ ] Ran migration down successfully
- [ ] Ran migration up again (repeatability check)
- [ ] No schema and data changes mixed
- [ ] Large table indexes use concurrent creation
- [ ] NOT NULL columns on existing tables have defaults
- [ ] Changes are backwards compatible with deployed code
- [ ] Considered zero-downtime deployment requirements
