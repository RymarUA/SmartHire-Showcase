# React Dashboard Architecture

SmartHire Dashboard is a React 19 + TypeScript control plane for superadmins to manage tenants, billing, modules, and analytics.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19+ | UI Framework |
| TypeScript | ~5.8 | Type safety |
| Vite | latest | Build tool |
| shadcn/ui | latest | Component library |
| TailwindCSS | latest | Styling |
| TanStack Query | latest | API data fetching |
| Lucide | latest | Icons |

## Project Structure

```
dashboard/
├── src/
│   ├── api/              # API client + queries
│   │   ├── client.ts     # Axios/fetch setup
│   │   └── queries/      # TanStack Query hooks
│   ├── components/
│   │   ├── ui/           # shadcn/ui components
│   │   └── dashboard/    # Dashboard-specific components
│   ├── pages/            # Route pages
│   ├── hooks/            # Custom hooks
│   ├── lib/              # Utilities
│   ├── types/            # TypeScript types
│   └── App.tsx           # Main app
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Key Pages

| Page | Route | Purpose |
|------|-------|---------|
| Overview | `/` | Revenue, active tenants, conversion rate |
| Tenants | `/tenants` | CRUD, enable/disable, modules, billing |
| Onboarding | `/onboarding` | 5-step wizard for new clients |
| Modules | `/modules` | Module Federation UI (enable/disable) |
| Billing | `/billing` | Plans, subscriptions, payments |
| Feature Flags | `/flags` | Per-tenant feature toggles |
| White Label | `/white-label` | Brand customization |
| Analytics | `/analytics` | Business metrics + Prometheus |
| Monitoring | `/monitoring` | Health dashboard + alerts |
| Webhooks | `/webhooks` | Webhook subscription management |

## API Integration

### TanStack Query Hook

```typescript
// src/api/queries/useTenants.ts
import { useQuery } from "@tanstack/react-query";

interface Tenant {
  id: string;
  name: string;
  status: "active" | "paused" | "cancelled";
  modules: string[];
}

export function useTenants() {
  return useQuery<Tenant[]>({
    queryKey: ["tenants"],
    queryFn: async () => {
      const res = await fetch("/api/v1/tenants");
      if (!res.ok) throw new Error("Failed to fetch tenants");
      return res.json();
    },
  });
}
```

### Using in Component

```typescript
// src/pages/Tenants.tsx
import { useTenants } from "@/api/queries/useTenants";

export function TenantsPage() {
  const { data: tenants, isLoading, error } = useTenants();

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div className="grid gap-4">
      {tenants?.map((tenant) => (
        <TenantCard key={tenant.id} tenant={tenant} />
      ))}
    </div>
  );
}
```

## Authentication

- JWT in httpOnly cookies (not localStorage)
- Dashboard auth via `dashboard_auth` router
- Session validation on each API call

```typescript
// src/api/client.ts
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}${path}`, {
    credentials: "include", // httpOnly cookies, not localStorage
    ...init,
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<T>;
}
```

## Component Example (shadcn/ui)

```typescript
// src/components/ui/card.tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
));
Card.displayName = "Card";

export { Card, CardHeader, CardTitle, CardContent };
```

## Running Dashboard

Frontends live in a pnpm + turbo monorepo (`packages/ui`, `api-client`,
`config`, `observability` shared across all four apps):

```bash
pnpm install --frozen-lockfile   # at repo root
pnpm --filter dashboard dev      # http://localhost:3000
```

## Building for Production

```bash
pnpm --filter dashboard build
# Output: dashboard/dist/
```

## References

- Dashboard: `dashboard/`
- API Client: `packages/api-client/`
- shadcn/ui: `packages/ui/`
