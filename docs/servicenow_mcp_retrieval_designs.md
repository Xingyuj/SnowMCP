# ServiceNow KB Retrieval / Chunking Design Options

Below are several possible designs for the MCP + ServiceNow Knowledge retrieval flow.

---

## Option 1 — ServiceNow Retrieval Only

**Use when:** ServiceNow Knowledge Search already returns sufficiently relevant articles/snippets.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Nexus as Nexus / AI Hub
    participant MCP as MCP Server
    participant SN as ServiceNow Knowledge API

    User->>Nexus: Ask natural-language question
    Nexus->>MCP: Call search_knowledge(query, user_context)
    MCP->>SN: Search KB using query + user identity
    SN->>SN: Apply ACL / User Criteria
    SN-->>MCP: Ranked articles / snippets
    MCP-->>Nexus: Return relevant KB content
    Nexus->>Nexus: Build context + generate answer
    Nexus-->>User: Final answer
```

### Characteristics

- No MCP-side chunking
- No BM25
- No embedding model
- No vector database
- Lowest implementation complexity
- Best option if ServiceNow already provides good retrieval and snippets

---

## Option 2 — ServiceNow Retrieval + Structure-Aware Chunking + BM25

**Use when:** ServiceNow can find the correct article, but the article body is too large to send directly to the LLM.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Nexus as Nexus / AI Hub
    participant MCP as MCP Server
    participant SN as ServiceNow Knowledge API
    participant Chunker as HTML / Section Chunker
    participant BM25 as BM25 Ranker

    User->>Nexus: Ask natural-language question
    Nexus->>MCP: Call search_knowledge(query, user_context)

    MCP->>SN: Search KB
    SN->>SN: Apply ACL / User Criteria
    SN-->>MCP: Top matching articles

    MCP->>SN: Get full article content
    SN-->>MCP: Article HTML / body

    MCP->>Chunker: Split by heading / paragraph / token limit
    Chunker-->>MCP: Structured chunks

    MCP->>BM25: Rank chunks against original query
    BM25-->>MCP: Top-K relevant chunks

    MCP-->>Nexus: Return top chunks + article metadata
    Nexus->>Nexus: Generate grounded answer
    Nexus-->>User: Final answer
```

### Characteristics

- ServiceNow remains responsible for article-level retrieval
- MCP only performs article-level content reduction
- Chunking can be deterministic:
  - H1 / H2 / H3
  - paragraphs
  - lists
  - token-size fallback
- BM25 provides lightweight intra-article ranking
- No embedding model
- No vector database
- No extra LLM call inside MCP

### Recommended first implementation

This is a strong default if ServiceNow returns whole articles rather than matched passages.

---

## Option 3 — MCP Semantic Retrieval with Embeddings

**Use when:** ServiceNow article-level retrieval is not sufficient and semantic matching is required inside the retrieved content.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Nexus as Nexus / AI Hub
    participant MCP as MCP Server
    participant SN as ServiceNow Knowledge API
    participant Embed as Embedding Model
    participant VS as Vector Store

    Note over MCP,VS: Offline / indexing flow

    MCP->>SN: Fetch authorised KB articles
    SN-->>MCP: Article content
    MCP->>MCP: Chunk articles
    MCP->>Embed: Generate embedding for each chunk
    Embed-->>MCP: Chunk vectors
    MCP->>VS: Store vectors + metadata + article IDs

    Note over User,VS: Online query flow

    User->>Nexus: Ask natural-language question
    Nexus->>MCP: Call semantic_search(query, user_context)

    MCP->>Embed: Generate query embedding
    Embed-->>MCP: Query vector

    MCP->>VS: Vector similarity search
    VS-->>MCP: Top-K semantic chunks

    MCP->>SN: Validate access / fetch authoritative content
    SN->>SN: Apply ACL / User Criteria
    SN-->>MCP: Authorised article content

    MCP-->>Nexus: Return relevant authorised chunks
    Nexus->>Nexus: Generate grounded answer
    Nexus-->>User: Final answer
```

### Characteristics

- Requires an embedding model
- Requires a vector index/store
- Requires KB synchronisation
- Requires re-indexing when content changes
- Requires careful ACL / User Criteria handling
- More operational complexity

### Important concern

If ServiceNow is the source of truth, the vector index must not become an ACL bypass.

---

## Option 4 — Hybrid Search: BM25 + Vector Search

**Use when:** High retrieval quality is required for both exact enterprise terms and natural-language semantic queries.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Nexus as Nexus / AI Hub
    participant MCP as MCP Server
    participant Embed as Embedding Model
    participant Search as Search Index
    participant SN as ServiceNow Knowledge API

    User->>Nexus: Ask natural-language question
    Nexus->>MCP: Call hybrid_search(query, user_context)

    par Keyword Retrieval
        MCP->>Search: BM25 search
        Search-->>MCP: Keyword-ranked results
    and Semantic Retrieval
        MCP->>Embed: Generate query embedding
        Embed-->>MCP: Query vector
        MCP->>Search: Vector similarity search
        Search-->>MCP: Semantic-ranked results
    end

    MCP->>MCP: Merge rankings (e.g. RRF)
    MCP->>MCP: Optional reranking

    MCP->>SN: Validate user access / fetch authoritative articles
    SN->>SN: Apply ACL / User Criteria
    SN-->>MCP: Authorised content

    MCP-->>Nexus: Return Top-K authorised chunks
    Nexus->>Nexus: Generate grounded answer
    Nexus-->>User: Final answer
```

### Characteristics

- BM25 handles:
  - KB IDs
  - product names
  - error codes
  - exact terminology
- Vector search handles:
  - synonyms
  - paraphrases
  - natural-language intent
- Usually higher retrieval quality than pure vector search
- Highest architectural complexity among these options

---

## Recommended Decision Path

```mermaid
flowchart TD
    A[ServiceNow Knowledge Search] --> B{Does it return good<br/>ranked snippets/passages?}

    B -->|Yes| C[Option 1<br/>Return ServiceNow results directly]
    B -->|No| D{Does it at least find<br/>the correct article?}

    D -->|Yes| E[Option 2<br/>Structure-aware chunking + BM25]
    D -->|No| F{Do we own retrieval<br/>and indexing?}

    F -->|No| G[Ask ServiceNow / AI Hub<br/>for semantic retrieval capability]
    F -->|Yes| H[Option 3 or 4<br/>Embedding / Hybrid Search]

    H --> I{Need exact IDs,<br/>error codes, product names?}
    I -->|Yes| J[Option 4<br/>Hybrid BM25 + Vector]
    I -->|No| K[Option 3<br/>Vector Search]
```

---

## Suggested Initial Architecture

For the current MCP integration, the preferred initial design is:

```text
ServiceNow Knowledge Search
        ↓
Top matching article(s)
        ↓
MCP fetches article content
        ↓
Structure-aware chunking
        ↓
Optional BM25 ranking
        ↓
Top relevant chunks
        ↓
Nexus / LLM
        ↓
Final answer
```

This keeps ServiceNow responsible for access control and article discovery while preventing the MCP from becoming a second full RAG platform prematurely.
