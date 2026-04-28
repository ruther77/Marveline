import { useState, useRef, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { Search, X } from 'lucide-react';
import { useSearch } from '@/api/queries/useSearch';
import type { SearchResult } from '@/types/search';

const TYPE_LABELS: Record<string, string> = {
  customer: 'Client',
  product: 'Produit',
  reservation: 'Réservation',
  invoice: 'Facture',
  devis: 'Devis',
};

export default function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const { data } = useSearch(q);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const handleSelect = (result: SearchResult) => {
    setOpen(false);
    setQ('');
    navigate({ to: result.url as never });
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700"
        aria-label="Rechercher"
      >
        <Search className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="relative flex items-center">
      <div className="flex items-center gap-2 bg-white border border-gray-300 rounded-lg px-4 py-1.5 shadow-sm w-64 md:w-80">
        <Search className="w-4 h-4 text-gray-400 shrink-0" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher…"
          className="flex-1 text-sm outline-none bg-transparent"
        />
        <button
          onClick={() => { setOpen(false); setQ(''); }}
          className="text-gray-400 hover:text-gray-600"
          aria-label="Fermer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {data && data.results.length > 0 && (
        <div className="absolute top-full left-0 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
          {data.results.map((result) => (
            <button
              key={`${result.type}-${result.id}`}
              onClick={() => handleSelect(result)}
              className="w-full text-left px-4 py-2.5 hover:bg-gray-50 flex items-start gap-4"
            >
              <span className="text-xs font-medium bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded mt-0.5 shrink-0">
                {TYPE_LABELS[result.type] ?? result.type}
              </span>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{result.title}</div>
                {result.subtitle && (
                  <div className="text-xs text-gray-500 truncate">{result.subtitle}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {data && q.trim().length >= 1 && data.results.length === 0 && (
        <div className="absolute top-full left-0 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="px-4 py-4 text-sm text-gray-500 text-center">Aucun résultat</div>
        </div>
      )}
    </div>
  );
}
