# Conventions — Frontend React/TypeScript

## React Query (TanStack Query)

```typescript
// Fetch avec React Query
const { data, isLoading, error } = useQuery({
    queryKey: ['products', page, search],
    queryFn: () => productsApi.list({ page, limit: 20, search }),
});

// Mutation
const createMutation = useMutation({
    mutationFn: (data: ProductCreate) => productsApi.create(data),
    onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['products'] });
        toast.success('Produit créé');
    },
    onError: (err) => {
        const detail = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail || 'Erreur inconnue';
        toast.error(detail);
    },
});
```

## Pattern Erreur Mutation (CRITIQUE)

```typescript
// CORRECT
onError: (err) => {
    const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Erreur inconnue';
    toast.error(detail);
}

// INTERDIT — ne jamais utiliser
onError: (error) => {
    toast.error((error as Error).message);  // ← INTERDIT
}
```

## Zustand Store

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface AuthState {
    user: User | null;
    token: string | null;
    setUser: (user: User) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        immer((set) => ({
            user: null,
            token: null,
            setUser: (user) => set((state) => { state.user = user; }),
            logout: () => set((state) => { state.user = null; state.token = null; }),
        })),
        { name: 'marveline-auth' }
    )
);

// Accès localStorage (format persist)
const raw = localStorage.getItem('marveline-auth');
const parsed = JSON.parse(raw);
const user = parsed.state.user;  // ← format { state: {...}, version: 0 }
```

## CSRF

```typescript
// GET /auth/csrf → récupérer le token CSRF
// Header automatique via interceptor axios : X-CSRF-Token
// Token stocké dans marveline-ui.state.csrfToken
```

## Typage API

```typescript
// Types depuis types/
import type { Product, ProductCreate, ProductUpdate, PaginatedResponse } from '@/types/product';

// API function
export const productsApi = {
    list: (params: { page: number; limit: number; search?: string }) =>
        api.get<PaginatedResponse<Product>>('/products/', { params }).then(r => r.data),
    create: (data: ProductCreate) =>
        api.post<Product>('/products/', data).then(r => r.data),
    update: (id: number, data: ProductUpdate) =>
        api.patch<Product>(`/products/${id}`, data).then(r => r.data),
    delete: (id: number) =>
        api.delete(`/products/${id}`),
};
```

## Composants — Règles

```typescript
// Props typées
interface ProductCardProps {
    product: Product;
    onEdit?: (id: number) => void;
    onDelete?: (id: number) => void;
}

// Pas de any, pas de @ts-ignore
// Préférer React.FC<Props> ou const Component = (props: Props) =>
```

## DashboardLayout — Accordion

```typescript
// Auto-open au chargement selon pathname
const [openMenus, setOpenMenus] = useState<string[]>(() => {
    // Initialiser avec les groupes actifs selon location.pathname
    return NAV_GROUPS.filter(g => g.items.some(i => location.pathname.startsWith(i.href)))
        .map(g => g.id);
});
```

## Dropdowns Clippés — Pattern Fix

```typescript
// Problème : dropdown dans overflow-x-auto clippé
// Solution : position fixed + getBoundingClientRect()
const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });

const openDropdown = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setDropdownPos({ top: rect.bottom + window.scrollY, left: rect.left });
    setOpen(true);
};

// Dropdown rendu avec position: fixed
<div style={{ position: 'fixed', top: dropdownPos.top, left: dropdownPos.left, zIndex: 1000 }}>
```

## Vitest / Tests Unitaires Frontend

```typescript
// Config : frontend/vite.config.ts (globals, jsdom, setup: ./src/test/setup.ts)
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

describe('ProductCard', () => {
    it('renders product name', () => {
        render(<ProductCard product={mockProduct} />);
        expect(screen.getByText('Mon Produit')).toBeInTheDocument();
    });
});
```

## Règles

- `getCategories()` : toujours passer `limit: 1000` explicitement (défaut backend = 100)
- Bundle : `bundle_price_cents` / `cleaning_fee_cents` (pas `bundle_price` / `cleaning_fee`)
- Pas de `console.log` en production — utiliser le logger configuré
- Types exportés depuis `src/types/index.ts`
- API functions dans `src/api/` — une fonction par domain
