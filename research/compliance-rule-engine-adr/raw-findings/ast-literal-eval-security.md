# Raw Finding: ast.literal_eval Security Limitations

## Source
- **Primary**: Python 3 Official Documentation
- **URL**: https://docs.python.org/3/library/ast.html#ast.literal_eval
- **Version**: Python 3.14.3 documentation (current)
- **Source Tier**: Tier 1 — Official Python language documentation

## Function Signature
```
ast.literal_eval(node_or_string)
```

## Official Description
> "Evaluate an expression node or a string containing only a Python literal or container display.
> The string or node provided may only consist of the following Python literal structures: strings,
> bytes, numbers, tuples, lists, dicts, sets, booleans, None and Ellipsis."

## Capability Constraints
- **NOT capable** of evaluating arbitrarily complex expressions
- Does NOT support operators (e.g., `>`, `<`, `and`, `or`, `==`)
- Does NOT support variable references
- Does NOT support function calls
- Does NOT support indexing
- Only handles: `str`, `bytes`, `int`, `float`, `complex`, `tuple`, `list`, `dict`, `set`, `bool`, `None`, `Ellipsis`

## Security Warning (Official Python Docs)
> **"This function had been documented as 'safe' in the past without defining what that meant.
> That was misleading."**
>
> "This is specifically designed not to execute Python code, unlike the more general eval(). There
> is no namespace, no name lookups, or ability to call out. **But it is not free from attack:**
> **A relatively small input can lead to memory exhaustion or to C stack exhaustion, crashing the**
> **process. There is also the possibility for excessive CPU consumption denial of service on some**
> **inputs. Calling it on untrusted data is thus not recommended.**"

## Official Warning Box
> **Warning**: "It is possible to crash the Python interpreter due to stack depth limitations in
> Python's AST compiler."

## Exceptions Raised on Malformed Input
- `ValueError`
- `TypeError`
- `SyntaxError`
- `MemoryError`
- `RecursionError`

## Version History
- **Python 3.2**: Now allows bytes and set literals
- **Python 3.9**: Now supports creating empty sets with `set()`
- **Python 3.10**: For string inputs, leading spaces and tabs are now stripped

## ADR Relevance
`ast.literal_eval` has significant limitations that make it unsuitable as a **compliance expression evaluator**:

1. **DoS risk**: Confirmed by official Python docs — small inputs can exhaust memory or crash the interpreter process
2. **Limited expressiveness**: Cannot evaluate comparison operators, which are fundamental to compliance rules (e.g., `value >= minimum`, `count < threshold`)
3. **Officially discouraged on untrusted input**: Python core developers explicitly state "calling it on untrusted data is thus not recommended"

If `simpleeval` (a more capable evaluator) is too dangerous, `ast.literal_eval` is too limited to be useful as a rule engine — it cannot even evaluate `properties.sku == "Standard"` since `==` is an operator.

## Practical Implication for Option 2
Any "Python expression evaluator" approach that needs to evaluate conditions like:
- `resource.properties.sku == 'Standard'`
- `resource.properties.retentionDays >= 30`
- `resource.tags contains 'environment'`

...cannot use `ast.literal_eval` (no operators). It **must** use a more capable evaluator
like `simpleeval` — which now has CVE-2026-32640 (CVSS 8.7 HIGH).
