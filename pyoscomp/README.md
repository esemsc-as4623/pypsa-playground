
**Legend**
> names of relevant pyoscomp module(s)
```mermaid
---
config:
    theme: 'neutral'
---
block
    A["A"]
    B["B"]
    C(["C"])
    D{{"D"}}

    classDef TODO color:#f66,stroke:#f66,stroke-width:2px
    class B TODO

    classDef dataclass fill:#6e6ce6,color:#fff
    class D dataclass
```

A, B = Class Object <span style="color:red">(TODO)</span>
C = Function or Class Method
D = DataClass Object

---
### 1. Scenario Authoring
> modules: `scenario`, `interfaces`
```mermaid
---
config:
    theme: 'neutral'
---
block
    columns 2
    block:scenario
        columns 3
        block:group1
            columns 1
            T1["TopologyComponent"]
            T2["TimeComponent"]
            T3["DemandComponent"]
            T4["SupplyComponent"]
            T5["PerformanceComponent"]
            T6["EconomicsComponent"]
            T7["StorageComponent"]
            T8["EmissionsComponent"]
            T9["TargetsComponent"]
        end

        classDef TODO color:#f66,stroke:#f66,stroke-width:2px
        class T7 TODO
        class T8 TODO
        class T9 TODO

        space

        block:group2
            columns 1
            space:3
            S1(["validate_scenario()"])
            S2(["Scenario.build()"])
            space:3
        end

        group1 --> group2
    end
    scenario --> D{{"ScenarioData"}}

    classDef dataclass fill:#6e6ce6,color:#fff
    class D dataclass
```
---
### 2. Translation to Model Input
> modules: `interfaces`, `translation`
---
### 3. Model Execution
> modules: `runners`
---
### 4. Translation of Model Output
> modules: `translation`, `interfaces`
---
### 5. Post-processing & Comparison
> 
---