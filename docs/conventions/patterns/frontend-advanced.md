# Patterns — Frontend Avancé

## Zod + Validation Formulaires

```typescript
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

const productSchema = z.object({
    name: z.string().min(1, 'Nom requis').max(200),
    price_cents: z.number().int().min(0, 'Prix doit être positif'),
    category_id: z.number().int().positive('Catégorie requise'),
    description: z.string().optional(),
});

type ProductFormData = z.infer<typeof productSchema>;

function ProductForm() {
    const { register, handleSubmit, formState: { errors } } = useForm<ProductFormData>({
        resolver: zodResolver(productSchema),
    });

    return (
        <form onSubmit={handleSubmit(onSubmit)}>
            <input {...register('name')} />
            {errors.name && <p>{errors.name.message}</p>}
        </form>
    );
}
```

## MSW Mock Service Worker (Tests)

```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
    http.get('/api/v1/products/', () => {
        return HttpResponse.json({
            items: [{ id: 1, name: 'Test Product', price_cents: 1500 }],
            total: 1, page: 1, limit: 20, pages: 1,
        });
    }),
    http.post('/api/v1/products/', async ({ request }) => {
        const data = await request.json();
        return HttpResponse.json({ id: 2, ...data }, { status: 201 });
    }),
];

// src/test/setup.ts
import { setupServer } from 'msw/node';
export const server = setupServer(...handlers);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

## useTransition / useDeferredValue (React 18)

```typescript
import { useTransition, useDeferredValue, useState } from 'react';

// useTransition : marquer mise à jour comme non urgente
function FilterableList() {
    const [isPending, startTransition] = useTransition();
    const [filter, setFilter] = useState('');

    const handleFilterChange = (value: string) => {
        startTransition(() => {
            setFilter(value);  // Non urgent — ne bloque pas l'UI
        });
    };

    return (
        <>
            <input onChange={e => handleFilterChange(e.target.value)} />
            {isPending && <Spinner />}
            <HeavyList filter={filter} />
        </>
    );
}

// useDeferredValue : différer une valeur pour éviter le debounce manuel
function SearchResults({ query }: { query: string }) {
    const deferredQuery = useDeferredValue(query);
    // deferredQuery se met à jour en arrière-plan, sans bloquer l'UI
    const { data } = useQuery({
        queryKey: ['search', deferredQuery],
        queryFn: () => api.search(deferredQuery),
    });
}
```

## URL State Sync

```typescript
import { useSearchParams } from 'react-router-dom';

function ProductsPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const page = Number(searchParams.get('page') || '1');
    const search = searchParams.get('search') || '';

    const updateFilters = (updates: Record<string, string>) => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            Object.entries(updates).forEach(([k, v]) => {
                if (v) next.set(k, v);
                else next.delete(k);
            });
            return next;
        });
    };

    return (
        <input
            value={search}
            onChange={e => updateFilters({ search: e.target.value, page: '1' })}
        />
    );
}
```

## Optimistic UI

```typescript
const queryClient = useQueryClient();

const updateMutation = useMutation({
    mutationFn: (data: { id: number; status: string }) =>
        reservationsApi.updateStatus(data.id, data.status),

    onMutate: async (variables) => {
        // Annuler les refetch en cours
        await queryClient.cancelQueries({ queryKey: ['reservations'] });

        // Snapshot de l'état actuel
        const previous = queryClient.getQueryData<Reservation[]>(['reservations']);

        // Mise à jour optimiste
        queryClient.setQueryData<Reservation[]>(['reservations'], (old) =>
            old?.map(r => r.id === variables.id ? { ...r, status: variables.status } : r) ?? []
        );

        return { previous };
    },

    onError: (err, variables, context) => {
        // Rollback en cas d'erreur
        queryClient.setQueryData(['reservations'], context?.previous);
        toast.error('Mise à jour échouée');
    },

    onSettled: () => {
        queryClient.invalidateQueries({ queryKey: ['reservations'] });
    },
});
```

## Infinite Scroll

```typescript
import { useInfiniteQuery } from '@tanstack/react-query';
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';

function InfiniteProductList() {
    const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
        queryKey: ['products', 'infinite'],
        queryFn: ({ pageParam = null }) => productsApi.listCursor({ cursor: pageParam }),
        getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    });

    const { ref: loadMoreRef } = useIntersectionObserver({
        onIntersect: () => hasNextPage && fetchNextPage(),
    });

    return (
        <>
            {data?.pages.flatMap(p => p.items).map(product => (
                <ProductCard key={product.id} product={product} />
            ))}
            <div ref={loadMoreRef}>
                {isFetchingNextPage && <Spinner />}
            </div>
        </>
    );
}
```

## Form Dirty Guard (Unsaved Changes)

```typescript
import { useEffect } from 'react';
import { useFormState } from 'react-hook-form';

function DirtyGuard({ isDirty }: { isDirty: boolean }) {
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (isDirty) {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [isDirty]);

    return null;
}

// Dans le formulaire
function MyForm() {
    const { formState: { isDirty } } = useForm();
    return (
        <>
            <DirtyGuard isDirty={isDirty} />
            {/* form fields */}
        </>
    );
}
```

## Result Type (Erreurs Typées)

```typescript
type Result<T, E = Error> =
    | { success: true; data: T }
    | { success: false; error: E };

async function safeApiCall<T>(fn: () => Promise<T>): Promise<Result<T>> {
    try {
        const data = await fn();
        return { success: true, data };
    } catch (err) {
        return { success: false, error: err as Error };
    }
}

// Utilisation
const result = await safeApiCall(() => productsApi.create(data));
if (!result.success) {
    toast.error(result.error.message);
    return;
}
console.log(result.data); // TypeScript sait que c'est T ici
```

## PWA (Progressive Web App)

```typescript
// vite.config.ts
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
    plugins: [
        VitePWA({
            registerType: 'autoUpdate',
            workbox: {
                globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
                runtimeCaching: [{
                    urlPattern: /^https:\/\/api\.marveline\.com\//,
                    handler: 'NetworkFirst',
                    options: { cacheName: 'api-cache', networkTimeoutSeconds: 10 },
                }],
            },
        }),
    ],
});
```

## React.memo — Stratégie

```typescript
// Mémoïser uniquement si :
// 1. Le composant re-rend fréquemment avec les mêmes props
// 2. Le rendu est coûteux (liste longue, graphique)

const ExpensiveProductList = memo(
    function ProductList({ products, onSelect }: Props) {
        return <>{products.map(p => <ProductRow key={p.id} product={p} onSelect={onSelect} />)}</>;
    },
    (prev, next) => prev.products === next.products && prev.onSelect === next.onSelect
);

// useCallback pour stabiliser les fonctions passées à memo
const handleSelect = useCallback((id: number) => {
    navigate(`/products/${id}`);
}, [navigate]);
```
