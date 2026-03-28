# HTMX SSE Extension & Performance Findings

## HTMX SSE Extension
- **Documentation**: https://htmx.org/extensions/sse/
- **Install**: `npm install htmx-ext-sse`
- **Bundle path**: `node_modules/htmx-ext-sse/dist/sse.js`

### Key Attributes
| Attribute | Purpose |
|-----------|---------|
| `hx-ext="sse"` | Install SSE extension on element |
| `sse-connect="<url>"` | URL of SSE server |
| `sse-swap="<event-name>"` | Swap content on named event |
| `hx-trigger="sse:<event-name>"` | Trigger HTTP callback on SSE event |
| `sse-close=<event-name>` | Close EventStream on event |

### Usage Patterns

**Basic:**
```html
<div hx-ext="sse" sse-connect="/chatroom" sse-swap="message">
    Contents updated in real time
</div>
```

**Unnamed events** (use default name `message`):
```html
<div hx-ext="sse" sse-connect="/event-source" sse-swap="message"></div>
```
Server sends: `data: <div>Content to swap</div>`

**Multiple events in same element:**
```html
<div hx-ext="sse" sse-connect="/server-url" sse-swap="event1,event2"></div>
```

**Multiple events in child elements:**
```html
<div hx-ext="sse" sse-connect="/server-url">
    <div sse-swap="event1"></div>
    <div sse-swap="event2"></div>
</div>
```

**Trigger HTTP request on SSE event:**
```html
<div hx-ext="sse" sse-connect="/events">
    <button hx-get="/api/data" hx-trigger="sse:data-ready">
        Refresh
    </button>
</div>
```

### Reconnection
- Extension has built-in reconnection logic
- Uses exponential backoff algorithm
- On top of browser's native EventSource reconnection
- Streams are "always as reliable as possible"

### Migration from Old `hx-sse`
| Old | New |
|-----|-----|
| `hx-sse=""` | `hx-ext="sse"` |
| `hx-sse="connect:<url>"` | `sse-connect="<url>"` |
| `hx-sse="swap:<EventName>"` | `sse-swap="<EventName>"` |

---

## sse-starlette (FastAPI SSE)
- **Version**: 3.3.3 (March 17, 2026)
- **PyPI**: https://pypi.org/project/sse-starlette/
- **Downloads**: 39M/week
- **License**: BSD
- **Python**: 3.10–3.13

### Core Features
- Standards Compliant (W3C SSE spec)
- Native Starlette/FastAPI support
- Async/Await built on modern patterns
- Automatic client disconnect detection
- Graceful shutdown with cooperative cleanup
- Thread safety (context-local event management)
- Multi-loop support (multiple asyncio event loops)

### API

**EventSourceResponse:**
```python
from sse_starlette import EventSourceResponse

async def sse_endpoint(request):
    return EventSourceResponse(generate_events())
```

**JSONServerSentEvent:**
```python
from sse_starlette import JSONServerSentEvent

event = JSONServerSentEvent(
    data={"field": "value"},  # Anything json.dumps serializable
)
```

**Custom Ping:**
```python
from sse_starlette import ServerSentEvent

def custom_ping():
    return ServerSentEvent(comment="Custom ping message")

return EventSourceResponse(
    generate_events(),
    ping=10,  # Ping every 10 seconds
    ping_message_factory=custom_ping,
)
```

---

## HTMX Infinite Scroll
- **Documentation**: https://htmx.org/examples/infinite-scroll/
- **Trigger**: `hx-trigger="revealed"` — fires when element scrolls into viewport
- **Swap**: `hx-swap="afterend"` — append content after trigger element
- **For overflow containers**: Use `intersect once` instead of `revealed`
- **Pattern**: Last row of results contains trigger for next page

## HTMX Lazy Loading
- **Documentation**: https://htmx.org/examples/lazy-load/
- **Trigger**: `hx-trigger="load"` — fires when element enters DOM
- **Indicator**: `class="htmx-indicator"` for loading states
- **Transition**: `.htmx-settling` CSS class for fade-in

## HTMX Accessibility (Official Docs)
- HTMX docs say: "htmx-based applications are very similar to normal HTML apps"
- Recommendations are generic:
  - Use semantic HTML
  - Ensure focus state is clearly visible
  - Associate text labels with all form fields
  - Maximize readability with appropriate fonts and contrast
- **Assessment**: Official guidance is sparse — project needs custom patterns
  (focus management after swaps, aria-live announcements, aria-busy states)

## HTMX hx-on Attribute
- `hx-on:click="..."` — inline event handler
- `hx-on::before-request` — shorthand for `hx-on:htmx:before-request`
- DOM attributes lowercase, so use kebab-case: `hx-on:htmx:before-request`
- Enables optimistic UI patterns (immediate visual feedback)
