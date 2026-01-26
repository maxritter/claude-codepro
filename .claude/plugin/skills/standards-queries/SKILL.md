--
name: Queries Standards
description: Write secure, optimized database queries using parameterized queries, eager loading to prevent N+1 problems, and strategic indexing for performance. Use this skill when writing SQL queries, ORM queries, database interactions, or optimizing data fetching logic. Apply when working with query files, repository patterns, data access layers, SQL statements, ORM methods (ActiveRecord, Sequelize, Prisma queries), JOIN operations, WHERE clauses, preventing SQL injection, implementing eager loading or includes, adding query timeouts, wrapping operations in transactions, or caching expensive queries. Use for any task involving database reads, writes, complex queries, query optimization, or data fetching performance.
---

# Queries Standards

**Core Rule:** Write secure, performant queries using parameterized statements, eager loading, and strategic indexing.

## When to use this skill

- When writing SQL queries or ORM query methods in any backend file
- When implementing repository patterns or data access layers
- When optimizing queries to prevent N+1 query problems using eager loading or joins
- When selecting specific columns instead of using SELECT * for performance
- When adding indexes to columns used in WHERE, JOIN, or ORDER BY clauses
- When implementing parameterized queries to prevent SQL injection vulnerabilities
- When wrapping related database operations in transactions for data consistency
- When setting query timeouts to prevent runaway queries
- When caching results of complex or frequently-executed queries
- When refactoring slow queries or investigating query performance issues

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle backend queries.

## SQL Injection Prevention - Mandatory

**NEVER concatenate user input into SQL strings.** Always use parameterized queries.

**Bad - Vulnerable to SQL injection:**
```python
# Python
query = f"SELECT * FROM users WHERE email = '{user_email}'"
cursor.execute(query)

# JavaScript
db.query(`SELECT * FROM users WHERE email = '${userEmail}'`)
```

**Good - Parameterized queries:**
```python
# Python with psycopg2
cursor.execute("SELECT * FROM users WHERE email = %s", (user_email,))

# Python with SQLAlchemy ORM
User.query.filter_by(email=user_email).first()
```

```javascript
// JavaScript with pg
db.query('SELECT * FROM users WHERE email = $1', [userEmail])

// JavaScript with Sequelize ORM
User.findOne({ where: { email: userEmail } })
```

```sql
-- Prepared statements in raw SQL
PREPARE user_query AS SELECT * FROM users WHERE email = $1;
EXECUTE user_query('user@example.com');
```

**This applies to ALL user input:** query parameters, form data, URL paths, headers, cookies.

## N+1 Query Problem - Detection and Prevention

**Problem:** Loading a collection then querying for each item's relations in a loop.

**Bad - N+1 queries:**
```python
# Fetches users (1 query), then posts for each user (N queries)
users = User.query.all()
for user in users:
    posts = user.posts  # Separate query per user
```

```javascript
// Fetches users (1 query), then posts for each user (N queries)
const users = await User.findAll()
for (const user of users) {
    const posts = await user.getPosts()  // Separate query per user
}
```

**Good - Eager loading:**
```python
# SQLAlchemy - single query with JOIN
users = User.query.options(joinedload(User.posts)).all()

# Or use selectinload for separate optimized query
users = User.query.options(selectinload(User.posts)).all()
```

```javascript
// Sequelize - eager loading with include
const users = await User.findAll({
    include: [{ model: Post }]
})

// Prisma - include relations
const users = await prisma.user.findMany({
    include: { posts: true }
})
```

**When to use each strategy:**
- `joinedload` / `include`: One-to-one or small one-to-many relations
- `selectinload` / separate query: Large one-to-many or many-to-many relations

## Select Only Required Columns

**Bad - Fetching unnecessary data:**
```python
users = User.query.all()  # Fetches all columns including large text fields
```

```javascript
const users = await User.findAll()  // Fetches all columns
```

**Good - Specific columns:**
```python
# SQLAlchemy
users = db.session.query(User.id, User.email, User.name).all()

# Or with load_only
users = User.query.options(load_only(User.id, User.email, User.name)).all()
```

```javascript
// Sequelize
const users = await User.findAll({
    attributes: ['id', 'email', 'name']
})

// Prisma
const users = await prisma.user.findMany({
    select: { id: true, email: true, name: true }
})
```

**Especially important when:**
- Tables have large TEXT/BLOB columns
- Fetching many rows
- Columns contain sensitive data not needed for the operation

## Indexing Strategy

**Add indexes for columns used in:**
- WHERE clauses (filtering)
- JOIN conditions
- ORDER BY clauses (sorting)
- Foreign keys

**Migration example:**
```python
# Python (Alembic/SQLAlchemy)
def upgrade():
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_posts_user_id', 'posts', ['user_id'])
    op.create_index('idx_posts_created_at', 'posts', ['created_at'])
```

```javascript
// JavaScript (Sequelize)
await queryInterface.addIndex('users', ['email'], {
    name: 'idx_users_email'
})
```

```sql
-- Raw SQL
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_created_at ON posts(created_at);
```

**Composite indexes for multi-column queries:**
```sql
-- For queries filtering by user_id AND status
CREATE INDEX idx_posts_user_status ON posts(user_id, status);
```

**Don't over-index:** Each index slows down writes. Only index columns frequently used in queries.

## Transactions for Data Consistency

**Use transactions when:**
- Multiple related writes must succeed or fail together
- Reading then writing based on that read (prevent race conditions)
- Updating multiple tables that must stay consistent

**Python (SQLAlchemy):**
```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    try:
        user = session.query(User).filter_by(id=user_id).with_for_update().first()
        user.balance -= amount
        transaction = Transaction(user_id=user_id, amount=amount)
        session.add(transaction)
        session.commit()
    except Exception:
        session.rollback()
        raise
```

**JavaScript (Sequelize):**
```javascript
const t = await sequelize.transaction()
try {
    const user = await User.findByPk(userId, { transaction: t, lock: true })
    user.balance -= amount
    await user.save({ transaction: t })
    await Transaction.create({ userId, amount }, { transaction: t })
    await t.commit()
} catch (error) {
    await t.rollback()
    throw error
}
```

**Use row-level locking (`with_for_update()` / `lock: true`) when reading data you'll modify to prevent race conditions.**

## Query Timeouts

**Set timeouts to prevent runaway queries from blocking resources.**

**Python (psycopg2):**
```python
cursor.execute("SET statement_timeout = 5000")  # 5 seconds
cursor.execute(long_running_query)
```

**JavaScript (pg):**
```javascript
await client.query('SET statement_timeout = 5000')  // 5 seconds
await client.query(longRunningQuery)
```

**ORM-level timeouts:**
```python
# SQLAlchemy
engine = create_engine(url, connect_args={'options': '-c statement_timeout=5000'})
```

**Typical timeout values:**
- Simple queries: 1-2 seconds
- Complex reports: 10-30 seconds
- Background jobs: 60+ seconds

## Query Caching

**Cache expensive queries that:**
- Run frequently with same parameters
- Compute aggregations or complex joins
- Query data that changes infrequently

**Python (with Redis):**
```python
import redis
import json

cache = redis.Redis()

def get_user_stats(user_id):
    cache_key = f"user_stats:{user_id}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Expensive query
    stats = db.session.query(
        func.count(Post.id),
        func.sum(Post.views)
    ).filter(Post.user_id == user_id).first()

    cache.setex(cache_key, 3600, json.dumps(stats))  # Cache 1 hour
    return stats
```

**JavaScript (with Redis):**
```javascript
const redis = require('redis')
const client = redis.createClient()

async function getUserStats(userId) {
    const cacheKey = `user_stats:${userId}`
    const cached = await client.get(cacheKey)
    if (cached) return JSON.parse(cached)

    // Expensive query
    const stats = await Post.findAll({
        where: { userId },
        attributes: [
            [sequelize.fn('COUNT', sequelize.col('id')), 'count'],
            [sequelize.fn('SUM', sequelize.col('views')), 'totalViews']
        ]
    })

    await client.setEx(cacheKey, 3600, JSON.stringify(stats))  // Cache 1 hour
    return stats
}
```

**Cache invalidation strategies:**
- Time-based expiration (TTL)
- Invalidate on write operations
- Use cache tags for related data

## Query Optimization Checklist

Before marking query work complete:

- [ ] All user input uses parameterized queries
- [ ] No N+1 queries (verified with query logging)
- [ ] Only required columns selected
- [ ] Indexes exist for WHERE/JOIN/ORDER BY columns
- [ ] Related writes wrapped in transactions
- [ ] Query timeout set appropriately
- [ ] Expensive queries cached if appropriate
- [ ] Tested with realistic data volumes

## Common Query Anti-Patterns

**Loading all records then filtering in application code:**
```python
# BAD - loads entire table into memory
all_users = User.query.all()
active_users = [u for u in all_users if u.status == 'active']

# GOOD - filter in database
active_users = User.query.filter_by(status='active').all()
```

**Multiple queries instead of JOIN:**
```python
# BAD - separate queries
user = User.query.get(user_id)
posts = Post.query.filter_by(user_id=user_id).all()

# GOOD - single query with join
user = User.query.options(joinedload(User.posts)).get(user_id)
```

**Using LIKE with leading wildcard:**
```sql
-- BAD - can't use index
SELECT * FROM users WHERE email LIKE '%@example.com'

-- GOOD - can use index
SELECT * FROM users WHERE email LIKE 'user@%'
```

## Testing Query Performance

**Enable query logging during development:**

```python
# SQLAlchemy
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

```javascript
// Sequelize
const sequelize = new Sequelize(database, username, password, {
    logging: console.log
})
```

**Use EXPLAIN to analyze query plans:**
```sql
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'user@example.com';
```

**Look for:**
- Sequential scans (should use indexes)
- High row counts
- Nested loops on large tables
- Missing indexes
