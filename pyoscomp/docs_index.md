# PyOSComp Documentation Index

Central navigation hub for module documentation.

## Quick Links

- [Package Overview](README.md)
- [Scenario Module](scenario/README.md)
- [Scenario Components](scenario/components/README.md)
- [Scenario Validation](scenario/validation/README.md)
- [Interfaces Module](interfaces/README.md)
- [Translation Module](translation/README.md)
- [Time Translation Submodule](translation/time/README.md)
- [Runners Module](runners/README.md)

## Navigation Graph

```mermaid
flowchart TD
    IDX[docs_index.md] --> ROOT[README.md]
    IDX --> SCN[scenario/README.md]
    IDX --> CMP[scenario/components/README.md]
    IDX --> VAL[scenario/validation/README.md]
    IDX --> INT[interfaces/README.md]
    IDX --> TRN[translation/README.md]
    IDX --> TIM[translation/time/README.md]
    IDX --> RUN[runners/README.md]

    ROOT --> SCN
    ROOT --> INT
    ROOT --> TRN
    ROOT --> RUN

    SCN --> CMP
    SCN --> VAL
    TRN --> TIM
```

## Suggested Start Paths

- New to the package: [Package Overview](README.md) -> [Scenario Module](scenario/README.md) -> [Interfaces Module](interfaces/README.md)
- Working on model translation: [Translation Module](translation/README.md) -> [Time Translation Submodule](translation/time/README.md) -> [Runners Module](runners/README.md)
- Working on scenario authoring: [Scenario Components](scenario/components/README.md) -> [Scenario Validation](scenario/validation/README.md)
