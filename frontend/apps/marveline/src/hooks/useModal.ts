import { useState, useCallback } from 'react';

export interface UseModalResult<T = undefined> {
  isOpen: boolean;
  data: T | null;
  open: (data?: T) => void;
  close: () => void;
  toggle: () => void;
}

/**
 * Hook pour gérer l'état d'un modal
 */
export function useModal<T = undefined>(
  initialOpen = false
): UseModalResult<T> {
  const [isOpen, setIsOpen] = useState(initialOpen);
  const [data, setData] = useState<T | null>(null);

  const open = useCallback((modalData?: T) => {
    if (modalData !== undefined) {
      setData(modalData);
    }
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    // Reset data après fermeture (avec délai pour l'animation)
    setTimeout(() => setData(null), 200);
  }, []);

  const toggle = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  return {
    isOpen,
    data,
    open,
    close,
    toggle,
  };
}

/**
 * Hook pour gérer plusieurs modals
 */
export type ModalId = string;

export interface MultiModalState<T = unknown> {
  id: ModalId | null;
  data: T | null;
}

export interface UseMultiModalResult<T = unknown> {
  activeModal: ModalId | null;
  data: T | null;
  isOpen: (id: ModalId) => boolean;
  open: (id: ModalId, data?: T) => void;
  close: () => void;
  toggle: (id: ModalId, data?: T) => void;
}

export function useMultiModal<T = unknown>(): UseMultiModalResult<T> {
  const [state, setState] = useState<MultiModalState<T>>({
    id: null,
    data: null,
  });

  const isOpen = useCallback(
    (id: ModalId) => state.id === id,
    [state.id]
  );

  const open = useCallback((id: ModalId, data?: T) => {
    setState({
      id,
      data: data ?? null,
    });
  }, []);

  const close = useCallback(() => {
    setState({ id: null, data: null });
  }, []);

  const toggle = useCallback(
    (id: ModalId, data?: T) => {
      if (state.id === id) {
        close();
      } else {
        open(id, data);
      }
    },
    [state.id, open, close]
  );

  return {
    activeModal: state.id,
    data: state.data,
    isOpen,
    open,
    close,
    toggle,
  };
}

/**
 * Hook pour modal de confirmation
 */
export interface ConfirmModalState<T = unknown> {
  isOpen: boolean;
  data: T | null;
  resolve: ((confirmed: boolean) => void) | null;
}

export interface UseConfirmModalResult<T = unknown> {
  isOpen: boolean;
  data: T | null;
  confirm: (data?: T) => Promise<boolean>;
  handleConfirm: () => void;
  handleCancel: () => void;
}

export function useConfirmModal<T = unknown>(): UseConfirmModalResult<T> {
  const [state, setState] = useState<ConfirmModalState<T>>({
    isOpen: false,
    data: null,
    resolve: null,
  });
  const { isOpen, data, resolve } = state;

  const confirm = useCallback((data?: T): Promise<boolean> => {
    return new Promise((resolve) => {
      setState({
        isOpen: true,
        data: data ?? null,
        resolve,
      });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    resolve?.(true);
    setState({ isOpen: false, data: null, resolve: null });
  }, [resolve]);

  const handleCancel = useCallback(() => {
    resolve?.(false);
    setState({ isOpen: false, data: null, resolve: null });
  }, [resolve]);

  return {
    isOpen,
    data,
    confirm,
    handleConfirm,
    handleCancel,
  };
}
