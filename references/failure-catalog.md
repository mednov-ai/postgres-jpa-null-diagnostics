# Failure catalog

## Contents

- PostgreSQL untyped null
- Collection parameter used as scalar and list
- Empty collection semantics
- Nullable scalar parameters
- Projection and fetch joins
- Pageable native queries
- Empirical compatibility baseline

## PostgreSQL untyped null

Typical message:

```text
SQLSTATE 42P18: could not determine data type of parameter $1
```

Representative reproduction:

```java
var statement = connection.prepareStatement("select ? is null");
statement.setObject(1, null);
statement.executeQuery();
```

PostgreSQL cannot infer the placeholder type from `IS NULL`. Bind an explicit JDBC type or cast the placeholder. A surrounding ORM may avoid this failure because it derives a JDBC type from the Java/Kotlin signature or a typed comparison elsewhere in the query.

## Collection parameter used as scalar and list

Pattern:

```sql
coalesce(:statuses, null) is null or entity.status.id in :statuses
```

This is suspicious because the same parameter participates in scalar function resolution and multi-valued `IN` binding. It is not proof of failure. Validate through the production repository API.

Direct `EntityManager.setParameter` can choose scalar conversion and report errors such as conversion of an `ArrayList` to `String`, while Spring Data may apply collection-aware binding to the same HQL text.

## Empty collection semantics

Define the contract before editing:

| Input | Contract A: absent filter | Contract B: match nothing |
| --- | --- | --- |
| `null` | all eligible rows | all eligible rows |
| empty | all eligible rows | no rows |
| singleton | matching rows | matching rows |
| multiple | matching rows | matching rows |

`null eq #items` implements Contract B for empty lists. A companion flag derived with `items.isNullOrEmpty()` implements Contract A.

## Nullable scalar parameters

Patterns involving dates, booleans, UUIDs, enums, and numeric IDs must be tested separately. If Hibernate derives a BasicType, `:value is null` may work without `COALESCE`. Raw pgJDBC has no Kotlin/Java method-signature metadata and may require `setNull(index, Types.…)`.

## Projection and fetch joins

A `fetch` join exists to hydrate an entity association. It normally adds no value to an interface or constructor projection and can complicate validation, duplicate rows, and count derivation. Acceptance varies by HQL shape and Hibernate version, so classify it as a maintainability or pagination risk unless execution proves a failure.

## Pageable native queries

Check both SQL statements. A working content query does not prove the generated or declared count query works. Verify:

- `count(distinct root.id)` where joins multiply rows;
- absence of `order by` in count SQL;
- identical filter semantics;
- list guard parameters present in both queries;
- physical names and projection aliases.

## Empirical compatibility baseline

The following was observed in a minimal integration lab, not established as a universal compatibility guarantee:

- Spring Boot 3.5.14
- Hibernate ORM 6.6.49.Final
- pgJDBC 42.7.9
- PostgreSQL 18.4
- Kotlin 2.1.21 / Java 17

Observed behavior:

- raw pgJDBC `setObject(null)` in `select ? is null` produced SQLSTATE `42P18`;
- typed `setNull(..., Types.BOOLEAN)` and `cast(? as boolean)` worked;
- a Spring Data JPQL repository method using collection `COALESCE` worked for null, empty, singleton, and multiple values;
- a manually bound `EntityManager` version could fail by attempting to convert a collection to a scalar string;
- native collection `COALESCE`, nullable scalar `COALESCE`, SpEL guards, and direct typed scalar null checks worked in the tested shapes.

Use this baseline to prevent blanket rules, then retest the target versions and query shapes.
