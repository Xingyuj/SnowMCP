# ServiceNow MCP Authentication Options

This document compares authentication patterns for:

`User -> Nexus / AI Hub -> Azure APIM -> MCP Server -> ServiceNow`

The key design question is:

> **Does ServiceNow trust Microsoft Entra ID as an issuer for inbound access tokens?**

---

## Architecture Decision Summary

```mermaid
flowchart TD
    A[User authenticated in Nexus] --> B[Entra ID issues Token A]
    B --> C[Token A audience = MCP]
    C --> D[APIM validates Token A]
    D --> E[MCP Server]

    E --> F{Does ServiceNow trust Entra ID<br/>as an access-token issuer?}

    F -->|Yes| G[Option 1: OAuth OBO]
    F -->|Yes, and token is directly acceptable| H[Option 3: Direct Entra Token]

    F -->|No| I[Option 2: JWT Bearer Assertion]
    F -->|No / fallback| J[Option 4: Service Identity + Trusted User Context]

    G --> K[Entra issues Token B<br/>audience = ServiceNow]
    K --> L[ServiceNow validates Entra token]

    H --> L

    I --> M[ServiceNow validates MCP-signed assertion]
    M --> N[ServiceNow issues its own access token]

    J --> O[ServiceNow authenticates MCP service identity<br/>and separately validates user context]

    L --> P[Map end user to sys_user]
    N --> P
    O --> P

    P --> Q[Apply ACL / User Criteria]
    Q --> R[Return permitted KB articles]
```

---

# Option 1 - OAuth On-Behalf-Of (OBO)

## When to use

Use this option when:

- Nexus obtains an Entra access token for the MCP API.
- ServiceNow is configured to trust Microsoft Entra ID.
- ServiceNow has an API/resource audience registered in Entra.
- ServiceNow can validate Entra-issued access tokens and map the end user to `sys_user`.

## Important

OBO does **not** remove the requirement for ServiceNow to trust Entra ID.

The exchanged downstream token is still issued by Entra:

```text
Token A
iss = Entra ID
aud = MCP

        OBO exchange

Token B
iss = Entra ID
aud = ServiceNow
```

ServiceNow must therefore validate:

- Entra issuer (`iss`)
- Entra signing key / JWKS
- ServiceNow audience (`aud`)
- expiry (`exp`)
- scopes / delegated permissions
- user identity claims

## Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Nexus / AI Hub
    participant E as Microsoft Entra ID
    participant A as Azure APIM
    participant M as MCP Server
    participant S as ServiceNow

    U->>N: Sign in / invoke agent

    N->>E: Request access token for MCP
    E-->>N: Token A<br/>iss = Entra ID<br/>aud = MCP<br/>user = Ethan

    N->>A: Call MCP with Token A

    A->>A: Validate Entra signature
    A->>A: Validate iss, aud, exp, scopes
    A->>M: Forward validated request / Token A

    M->>E: OBO exchange<br/>Token A + MCP client credential

    E-->>M: Token B<br/>iss = Entra ID<br/>aud = ServiceNow<br/>user = Ethan

    M->>S: Call Knowledge API with Token B

    S->>S: Validate Entra signature using JWKS
    S->>S: Validate iss, aud, exp, scopes
    S->>S: Map Entra user claim to sys_user
    S->>S: Apply ACL / User Criteria

    S-->>M: Permitted KB articles
    M-->>A: MCP tool result
    A-->>N: Response
    N-->>U: Final response
```

## Trust relationship

```text
APIM trusts Entra
MCP trusts APIM / validated Entra identity
ServiceNow trusts Entra
```

---

# Option 2 - JWT Bearer Assertion to ServiceNow

## When to use

Use this option when:

- ServiceNow does not directly accept Entra access tokens for the Knowledge API.
- ServiceNow supports JWT Bearer Grant / JWT-based token exchange.
- ServiceNow can trust the MCP application's signing certificate/public key.
- ServiceNow can map the assertion's `sub` claim to a `sys_user`.

## Important

In this model, the user first authenticates through Entra, but the final Knowledge API access token is issued by ServiceNow.

The MCP Server does **not** forward the Entra token to the Knowledge API.

Instead:

1. MCP validates or receives a trusted Entra user identity.
2. MCP creates a signed JWT assertion.
3. ServiceNow validates the assertion.
4. ServiceNow issues its own access token.
5. MCP calls the Knowledge API with the ServiceNow token.

## Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Nexus / AI Hub
    participant E as Microsoft Entra ID
    participant A as Azure APIM
    participant M as MCP Server
    participant T as ServiceNow Token Endpoint
    participant S as ServiceNow Knowledge API

    U->>N: Sign in / invoke agent

    N->>E: Request access token for MCP
    E-->>N: Entra Token<br/>aud = MCP<br/>user = Ethan

    N->>A: Call MCP with Entra Token

    A->>A: Validate Entra token
    A->>M: Forward validated request

    M->>M: Extract trusted user identity<br/>oid / email / subject

    M->>M: Create JWT assertion<br/>iss = MCP client<br/>sub = Ethan<br/>aud = ServiceNow token endpoint

    M->>M: Sign assertion with MCP private key

    M->>T: JWT Bearer Grant<br/>signed assertion

    T->>T: Verify MCP signature
    T->>T: Validate iss, aud, exp
    T->>T: Map sub to sys_user

    T-->>M: ServiceNow-issued access token<br/>effective user = Ethan

    M->>S: Call Knowledge API<br/>ServiceNow access token

    S->>S: Validate ServiceNow token
    S->>S: Apply ACL / User Criteria

    S-->>M: Permitted KB articles
    M-->>A: MCP tool result
    A-->>N: Response
    N-->>U: Final response
```

## Trust relationship

```text
APIM trusts Entra

ServiceNow does NOT need to accept the Entra access token directly.

ServiceNow trusts:
MCP signing certificate / public key
        ↓
JWT assertion
        ↓
ServiceNow issues its own access token
```

---

# Option 3 - ServiceNow Directly Accepts the Same Entra Token

## When to use

Use this option only when ServiceNow is explicitly configured to accept the Entra token already presented to APIM / MCP.

This requires ServiceNow to trust:

- the Entra tenant / issuer
- Entra JWKS signing keys
- the token audience
- the relevant user claims

## Critical audience issue

This is only valid if the same token is legitimately intended for ServiceNow.

For example, this token is normally **not** sufficient:

```text
iss = Entra ID
aud = MCP
```

ServiceNow should normally reject it because:

```text
aud != ServiceNow
```

Therefore this design requires an explicit ServiceNow / Entra configuration that makes the token acceptable to both components, or another architecture where APIM is validating a token whose intended protected resource is also compatible with ServiceNow.

Do not assume that a valid Entra signature alone is sufficient.

## Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Nexus / AI Hub
    participant E as Microsoft Entra ID
    participant A as Azure APIM
    participant M as MCP Server
    participant S as ServiceNow

    U->>N: Sign in / invoke agent

    N->>E: Request Entra access token
    E-->>N: Entra token

    N->>A: Call MCP with Entra token

    A->>A: Validate Entra signature
    A->>A: Validate iss, aud, exp
    A->>M: Forward same token

    M->>S: Call Knowledge API with same Entra token

    S->>S: Validate Entra signature using JWKS
    S->>S: Validate trusted issuer
    S->>S: Validate acceptable audience
    S->>S: Map Entra user claim to sys_user
    S->>S: Apply ACL / User Criteria

    S-->>M: Permitted KB articles
    M-->>A: MCP tool result
    A-->>N: Response
    N-->>U: Final response
```

## Trust relationship

```text
APIM trusts Entra
ServiceNow also trusts Entra
```

This is simpler operationally, but the `aud` design must be explicitly confirmed.

---

# Option 4 - MCP Service Identity + Trusted User Context

## When to use

Use this option when:

- MCP authenticates to ServiceNow using a service account / service identity.
- ServiceNow does not directly use the user's Entra access token.
- The end-user identity must still be propagated separately.
- ServiceNow has a supported and trusted mechanism for resolving that user context.

## Important

A plain header such as:

```text
X-End-User: ethan@company.com
```

must not be trusted by itself.

The user context must be cryptographically protected or otherwise guaranteed by a trusted gateway/channel.

Examples:

- signed user-context JWT
- mutually authenticated trusted proxy
- APIM-generated signed identity context
- ServiceNow-supported impersonation/delegation mechanism

## Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant N as Nexus / AI Hub
    participant E as Microsoft Entra ID
    participant A as Azure APIM
    participant M as MCP Server
    participant S as ServiceNow

    U->>N: Sign in / invoke agent

    N->>E: Request access token for MCP
    E-->>N: Entra token<br/>user = Ethan

    N->>A: Call MCP

    A->>A: Validate Entra user token
    A->>M: Forward trusted user identity

    M->>M: Authenticate as MCP service identity

    M->>M: Create trusted user context<br/>effective user = Ethan

    M->>M: Optionally sign user-context JWT

    M->>S: Service credential<br/>+ trusted user context

    S->>S: Validate MCP service identity
    S->>S: Validate user-context integrity
    S->>S: Resolve effective user = Ethan
    S->>S: Apply ACL / User Criteria

    S-->>M: Permitted KB articles
    M-->>A: MCP tool result
    A-->>N: Response
    N-->>U: Final response
```

## Trust relationship

```text
ServiceNow authenticates:
MCP service identity

ServiceNow authorizes against:
trusted propagated end-user identity
```

This design requires particularly careful security review because authentication identity and effective user identity are separate.

---

# Comparison

| Option | Final API Token Issuer | Does ServiceNow Need to Trust Entra Access Tokens? | Preserves End-User Context? | Main Requirement |
|---|---|---:|---:|---|
| 1. OBO | Entra ID | Yes | Yes | ServiceNow must accept Entra token with `aud = ServiceNow` |
| 2. JWT Bearer Assertion | ServiceNow | No, not for final API token | Yes | ServiceNow trusts MCP-signed assertion and maps `sub` to `sys_user` |
| 3. Direct Entra Token | Entra ID | Yes | Yes | Same token must have an audience ServiceNow legitimately accepts |
| 4. Service Identity + User Context | Usually ServiceNow / service credential provider | No | Potentially | Trusted user-context propagation / impersonation mechanism |

---

# Recommended Decision Order

```mermaid
flowchart TD
    A[Need ServiceNow KB access with end-user permissions] --> B{Does ServiceNow accept<br/>Entra-issued access tokens?}

    B -->|Yes| C{Can MCP obtain a proper<br/>ServiceNow-audience token via OBO?}
    C -->|Yes| D[Use Option 1<br/>OBO]
    C -->|No| E{Can the same Entra token<br/>legitimately be accepted by ServiceNow?}
    E -->|Yes| F[Use Option 3<br/>Direct Entra Token]
    E -->|No| G[Review Entra / ServiceNow integration]

    B -->|No| H{Does ServiceNow support<br/>JWT Bearer Grant?}
    H -->|Yes| I[Use Option 2<br/>JWT Bearer Assertion]
    H -->|No| J[Consider Option 4<br/>Service Identity + Trusted User Context]
```

---

# Questions for the ServiceNow Team

1. **Is our ServiceNow instance configured to trust Microsoft Entra ID as an issuer for inbound OAuth access tokens?**

2. **If yes, what Entra audience must the token contain for the ServiceNow Knowledge API?**

3. **Does ServiceNow validate Entra tokens using Entra JWKS / signing keys?**

4. **Which Entra claim is mapped to `sys_user` — `oid`, `sub`, email, UPN, or another claim?**

5. **Can an MCP backend use OAuth On-Behalf-Of to obtain a ServiceNow-audience Entra token?**

6. **If ServiceNow does not directly accept Entra access tokens, does the instance support OAuth JWT Bearer Grant?**

7. **For JWT Bearer Grant, can the assertion `sub` be mapped to the target `sys_user` so that ACL and User Criteria run as that user?**

8. **When calling the Knowledge API, are ACL and Knowledge User Criteria evaluated against the effective authenticated user?**

9. **Is there an approved service-account plus trusted-user-context / impersonation pattern already used internally?**

---

# Core Security Requirement

Regardless of the selected option, the following identity chain must remain trustworthy:

```text
Nexus authenticated user
        =
MCP effective end user
        =
ServiceNow sys_user
        =
User evaluated by ACL / User Criteria
```

If ServiceNow only sees a shared MCP service account and does not have a trusted effective-user mechanism, all users may end up receiving the same ServiceNow permissions.
