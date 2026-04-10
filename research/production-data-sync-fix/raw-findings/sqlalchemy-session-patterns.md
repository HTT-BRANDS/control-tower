# SQLAlchemy Session Error Handling Patterns

**Source**: SQLAlchemy 2.0 Official Documentation (Tier 1)  
**URLs**:
- https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint
- https://docs.sqlalchemy.org/en/20/orm/session_basics.html#session-frequently-asked-questions

## Using SAVEPOINT (session.begin_nested())

### Official Documentation Quote

> SAVEPOINT transactions, if supported by the underlying engine, may be delineated using the
> `Session.begin_nested()` method.

> Each time `Session.begin_nested()` is called, a new "BEGIN SAVEPOINT" command is emitted to
> the database within the scope of the current database transaction (starting one if not
> already in progress), and an object of type `SessionTransaction` is returned, which
> represents a handle to this SAVEPOINT. When the `.commit()` method on this object is called,
> "RELEASE SAVEPOINT" is emitted to the database, and if instead the `.rollback()` method is
> called, "ROLLBACK TO SAVEPOINT" is emitted. The enclosing database transaction remains in
> progress.

### Official Code Example — Per-Record Error Handling

```python
from sqlalchemy import exc

with session.begin():
    for record in records:
        try:
            with session.begin_nested():
                obj = SomeRecord(id=record["identifier"], name=record["name"])
                session.add(obj)
        except exc.IntegrityError:
            print(f"Skipped record {record} – row already exists")
```

### Official Statement on Use Case

> `Session.begin_nested()` is typically used as a context manager where specific per-instance
> errors may be caught, in conjunction with a rollback emitted for that portion of the
> transaction's state, without rolling back the whole transaction.

> This pattern is ideal for situations such as using PostgreSQL and catching `IntegrityError`
> to detect duplicate rows; PostgreSQL normally aborts the entire transaction when such an
> error is raised, however when using SAVEPOINT, the outer transaction is maintained.

### Flush Behavior

> When `Session.begin_nested()` is called, the `Session` first flushes all currently pending
> state to the database, unconditionally, regardless of the value of the `Session.autoflush`
> parameter which normally may be used to disable automatic flush. The rationale for this
> behavior is so that when a rollback on this nested transaction occurs, the `Session` may
> expire any in-memory state that was created within the scope of the SAVEPOINT, while
> ensuring that when those expired objects are refreshed, the state of the object graph prior
> to the beginning of the SAVEPOINT will be available to re-load from the database.

### State Management After Rollback

> In modern versions of SQLAlchemy, when a SAVEPOINT initiated by `Session.begin_nested()` is
> rolled back, in-memory object state that was modified since the SAVEPOINT was created is
> expired, however other object state that was not altered is not changed.

## Session Lifecycle FAQ

### Official Recommendation

> As a general rule, keep the lifecycle of the session **separate and external** from functions
> and objects that access and/or manipulate database data. This will greatly help with
> achieving a predictable and consistent transactional scope.

> Make sure you have a clear notion of where transactions begin and end, and keep transactions
> **short**, meaning, they end at the series of operations, instead of being held open
> indefinitely.

### Anti-Pattern Warning

The docs explicitly show "wrong way" and "better way":

**Wrong** — session created inside each function:
```python
### this is the **wrong way to do it** ###
class ThingOne:
    def go(self):
        session = Session()
        try:
            session.execute(update(FooBar).values(x=5))
            session.commit()
        except:
            session.rollback()
            raise
```

**Better** — session managed externally:
```python
### this is a **better** (but not the only) way to do it ###
class ThingOne:
    def go(self, session):
        session.execute(update(FooBar).values(x=5))

def run_my_program():
    with Session() as session:
        with session.begin():
            ThingOne().go(session)
            ThingTwo().go(session)
```

## Azure SQL / MSSQL SAVEPOINT Support

SQL Server and Azure SQL fully support SAVEPOINT transactions:
- `SAVE TRANSACTION savepoint_name` — creates savepoint
- `ROLLBACK TRANSACTION savepoint_name` — rolls back to savepoint
- SQLAlchemy's `begin_nested()` automatically uses the correct dialect

**Note**: Azure SQL S0 tier supports SAVEPOINTs without any restrictions.

## Handling PendingRollbackError

`PendingRollbackError` occurs when you try to use a session that is in a failed
transaction state (needs rollback). This typically happens when:

1. An exception occurs during a flush
2. The session's transaction is now in an invalid state
3. Subsequent operations on the same session raise `PendingRollbackError`

**Prevention**: Always use `begin_nested()` for operations that might fail, so the
session's outer transaction remains valid after a nested rollback.

**Recovery**: If you encounter `PendingRollbackError`, call `session.rollback()` to
clear the failed state, then retry.
