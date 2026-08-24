# Integration lab protocol

## Contents

- Required stack
- Minimal model
- Test matrix
- Evidence collection
- Completion criteria

## Required stack

Use the target Spring Boot dependency management and its Hibernate/Spring Data versions. Pin pgJDBC and PostgreSQL explicitly in the test report. Use Testcontainers or embedded PostgreSQL; do not substitute H2 for the decisive run.

## Minimal model

Create only entities, columns, joins, and projections required by the query under test. Preserve these production characteristics:

- Kotlin nullability and collection type;
- named parameter reuse;
- JPQL versus native mode;
- projection return type;
- inheritance/discriminator usage when relevant;
- Pageable and Sort arguments;
- database column types.

Call the repository interface from a Spring test. A separate low-level JDBC test is useful for isolating driver behavior but does not replace the repository test.

## Test matrix

For every nullable collection, exercise:

```text
null
emptyList()
listOf(oneValue)
listOf(firstValue, secondValue)
```

For scalar nullable parameters, exercise null and at least one non-null value. For booleans, include all three states. Assert returned identifiers or ordered values, not only row counts.

For pageable methods, assert content, total elements, total pages, and a nonzero page offset. For projections, access every projected property so deferred conversion errors surface.

## Evidence collection

Enable generated SQL and JDBC bind logging only for diagnosis. Capture:

- root exception class and message;
- PostgreSQL SQLSTATE;
- generated SQL for content and count;
- parameter value category and inferred JDBC type;
- expected and actual row identifiers.

Redact credentials and business data before saving logs.

## Completion criteria

A fix is verified only when:

- the original failure is reproduced or explicitly marked non-reproducible;
- every relevant parameter case has an assertion;
- the test uses real PostgreSQL;
- production repository binding is exercised;
- query results preserve the intended filter contract;
- the final report separates confirmed failures from static risks.
