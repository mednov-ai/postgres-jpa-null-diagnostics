---
name: postgres-jpa-null-diagnostics
description: Diagnose and fix PostgreSQL parameter type errors and nullable-filter failures in Spring Boot, Spring Data JPA, Hibernate, JPQL/HQL, native SQL, Kotlin/Java repositories, and raw pgJDBC. Use for errors such as SQLSTATE 42P18, "could not determine data type of parameter", collection parameters used in COALESCE or IN, nullable dates/booleans/UUIDs, empty-list semantics, projection/fetch-join failures, pageable native queries, or framework/driver upgrades that change query behavior.
---

# PostgreSQL JPA null diagnostics

Determine the failing layer before changing a query. Verify uncertain behavior with the real repository method and a real PostgreSQL instance; do not infer Spring Data behavior from an `EntityManager` or H2-only reproduction.

## Workflow

1. Record exact versions of Spring Boot, Spring Data JPA, Hibernate, pgJDBC, Kotlin/Java, and PostgreSQL.
2. Locate repository declarations, parameter types, callers, projections, entity mappings, physical table names, and pagination arguments.
3. Run `python3 scripts/scan_queries.py <project-root>` for an initial inventory. Treat its findings as investigation targets, not proof of defects.
4. Classify the failure layer:
   - PostgreSQL parser/type inference and SQLSTATE;
   - pgJDBC binding (`setObject(null)` versus typed `setNull`);
   - Hibernate HQL validation or parameter conversion;
   - Spring Data repository binding, projection conversion, or derived count query;
   - application-level `null` versus empty-collection semantics.
5. Reproduce through the same entry point used in production. If production calls a Spring Data repository method, the decisive test must call that method.
6. Test the applicable matrix:
   - nullable scalar: `null` and representative non-null values;
   - collection: `null`, empty, singleton, and multiple values;
   - boolean: `null`, `false`, and `true`;
   - pageable query: content query and count query;
   - projection: rows with and without optional joins.
7. Capture the root exception, SQLSTATE, generated SQL, bind types, and returned row IDs. Distinguish a crash from an unintended result set.
8. Apply the smallest fix that preserves the declared filter contract.
9. Rerun the complete matrix on PostgreSQL and report verified behavior separately from static concerns.

Read [references/failure-catalog.md](references/failure-catalog.md) when selecting a fix. Read [references/lab-protocol.md](references/lab-protocol.md) when building or reviewing an integration reproducer.

## Fix selection

### Raw pgJDBC untyped null

Prefer an explicit JDBC type:

```java
statement.setNull(index, Types.BOOLEAN);
```

Alternatively cast the placeholder where the SQL type is part of the query contract:

```sql
cast(? as boolean)
```

Do not use `setObject(index, null)` for a placeholder whose type PostgreSQL cannot infer.

### JPQL collection filters

Do not automatically declare `COALESCE(:items, NULL)` invalid. Spring Data and direct `EntityManager` binding can behave differently, and behavior is version-dependent.

Prefer one of these only after testing:

```kotlin
(:#{null eq #items} = true or entity.code in :items)
```

or construct the predicate dynamically with Specification/Criteria/Querydsl. State explicitly whether an empty collection means “no filter” or “match nothing.” The SpEL example treats only `null` as absent.

### Native collection filters

Use an explicit scalar guard when `null` and empty both mean “no filter”:

```sql
:itemsAbsent = true or table_name.code in (:items)
```

```kotlin
@Param("itemsAbsent") itemsAbsent: Boolean = items.isNullOrEmpty()
```

Test that the ORM still binds an acceptable placeholder for the inactive `IN` branch.

### Nullable scalar filters

First test the direct form:

```sql
:value is null or table_name.column_name = :value
```

Hibernate often knows the type from the repository signature and typed comparison. `COALESCE(:value, NULL)` is not automatically required and is not a universal cure for untyped JDBC nulls.

### Projections, fetch joins, and pagination

Remove `fetch` when selecting a scalar/interface/DTO projection unless entity hydration needs it. For native pageable queries, provide and test an explicit `countQuery`. Verify aliases against projection accessor names and physical column names.

## Guardrails

- Never validate PostgreSQL-specific behavior only on H2.
- Never replace every `COALESCE` mechanically.
- Never treat `null` and an empty collection as equivalent without confirming the API contract.
- Never claim a query is fixed from startup validation alone; execute it with representative bindings.
- Never test only generated SQL while bypassing Spring Data if production uses Spring Data.
- Preserve unrelated query semantics, ordering, distinctness, pagination, and projection aliases.

## Result format

Return:

1. tested version matrix;
2. confirmed failures with root exception and SQLSTATE;
3. parameter-case table (`null`, empty, singleton, multiple);
4. semantic changes introduced by each candidate fix;
5. minimal patch recommendation;
6. residual risks requiring the production schema or mappings.

If no defect is reproduced, say so explicitly and recommend no production patch. List missing matrix cases as test gaps rather than converting them into assumed failures.
