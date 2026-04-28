// Auth
export { useAuth } from './useAuth';

// State management
export { useLocalStorage, useSessionStorage } from './useLocalStorage';
export { useModal, useMultiModal, useConfirmModal } from './useModal';
export type { UseModalResult, UseMultiModalResult, UseConfirmModalResult } from './useModal';

// Data handling
export { usePagination, useClientPagination } from './usePagination';
export type { PaginationState, PaginationResult, UsePaginationOptions } from './usePagination';

export { useSort, useClientSort } from './useSort';
export type { SortDirection, SortState, UseSortOptions, UseSortResult } from './useSort';

export { useFilter, useClientFilter, filterUtils } from './useFilter';
export type { FilterValue, FilterState, UseFilterOptions, UseFilterResult } from './useFilter';

// Utilities
export { useDebounce } from './useDebounce';
export { useToast } from '@shared/components/ui/Toast';
export { useClipboard, useClipboardRead } from './useClipboard';
export type { UseClipboardOptions, UseClipboardResult, UseClipboardReadResult } from './useClipboard';

export { useOnClickOutside, useOnClickOutsideMultiple, useClickOutsideState } from './useOnClickOutside';

export { useMediaQuery, useBreakpoint, useCurrentBreakpoint, useResponsive, breakpoints } from './useMediaQuery';
export type { Breakpoint } from './useMediaQuery';

export { useAsync, useAsyncRetry, usePolling } from './useAsync';
export type { AsyncStatus, AsyncState, UseAsyncResult, UseAsyncRetryOptions } from './useAsync';

export { useKeyPress, useKeyboardShortcuts, useEscapeKey, useEnterKey, useArrowNavigation, useListNavigation } from './useKeyboard';
export type { KeyboardShortcut } from './useKeyboard';

export { useNetworkStatus } from './useNetworkStatus';

export { useHasScope, useHasAnyScope, useHasAllScopes } from './useHasScope';
