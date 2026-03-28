# TechEmpower Framework Benchmarks — Round 22

**Source**: https://www.techempower.com/benchmarks/#hw=ph&test=fortune&section=data-r22
**Date**: October 17, 2023 (Round 22)
**Test**: Fortunes (most realistic web workload — database query + HTML template rendering)
**Total Frameworks**: 301

## Relevant Framework Rankings

### Top Tier (Compiled / Systems Languages)
| Rank | Framework | Language | Requests/sec | Relative |
|------|-----------|----------|-------------|----------|
| 23 | asp.net core | C# (.NET) | 342,523 | 58.5% |
| 24 | fasthttp-prefork | Go | 338,620 | 57.9% |
| 29 | fiber-prefork | Go | 328,620 | 56.2% |
| 30 | hyper-db | Rust | 322,352 | 55.1% |
| 31 | beetlex-core-updb | C# (.NET) | 313,449 | 53.6% |
| 37 | gearbox | Go | 306,291 | 52.3% |
| 41 | fasthttp | Go | 294,953 | 50.4% |
| 46 | fiber | Go | 276,309 | 47.2% |

### Mid Tier (JVM / Node.js)
| Rank | Framework | Language | Requests/sec | Relative |
|------|-----------|----------|-------------|----------|
| 245 | nodejs-chakra | JavaScript | 64,992 | 11.1% |
| 246 | nodejs | JavaScript | 64,779 | 11.1% |
| 260 | nestjs-fastify | TypeScript | 61,081 | 10.4% |
| 267 | nestjs-fastify-mysql | TypeScript | 58,907 | 10.1% |

### Python Tier
| Rank | Framework | Language | Requests/sec | Relative |
|------|-----------|----------|-------------|----------|
| 264 | granian [rsgi] | Python | 59,551 | 10.2% |
| 302 | granian [asgi] | Python | 47,932 | 8.2% |
| 306 | **fastapi** | **Python** | **46,896** | **8.0%** |
| 314 | **fastapi-uvicorn** | **Python** | **44,605** | **7.6%** |
| 320 | aiohttp-pg-raw | Python | 42,020 | 7.2% |

### Key Takeaways

1. **ASP.NET Core is 7.3x faster than FastAPI** in raw throughput
2. **Go frameworks are 6-7x faster than FastAPI** in raw throughput
3. **Node.js is ~1.4x faster than FastAPI** in raw throughput
4. **Performance is IRRELEVANT at 10-30 users** — even FastAPI handles 47K req/s

### Why Benchmarks Don't Matter Here

The governance platform handles:
- ~30 concurrent requests maximum (10-30 users, most viewing dashboards)
- Most time is spent waiting for Azure API responses (I/O bound, not CPU bound)
- Database queries are simple CRUD (10ms per query, not microsecond-sensitive)
- Template rendering for ~50 pages is negligible

**Even the "slowest" Python framework handles 1,000x more traffic than this platform will ever see.**

### Real Performance Bottlenecks (Not Framework Related)
1. Azure API response times (200-2000ms per call)
2. Azure SQL query times (10-100ms per query)
3. Network latency to Azure services
4. Template rendering with large datasets (Jinja2 streaming could help)

None of these would improve by switching frameworks.
