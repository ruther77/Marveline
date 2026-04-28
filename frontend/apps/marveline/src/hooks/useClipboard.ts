import { useState, useCallback } from 'react';

export interface UseClipboardOptions {
  timeout?: number;
  onSuccess?: (text: string) => void;
  onError?: (error: Error) => void;
}

export interface UseClipboardResult {
  copied: boolean;
  copy: (text: string) => Promise<boolean>;
  error: Error | null;
}

/**
 * Hook pour copier du texte dans le presse-papier
 */
export function useClipboard(options: UseClipboardOptions = {}): UseClipboardResult {
  const { timeout = 2000, onSuccess, onError } = options;
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      try {
        // Méthode moderne
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
        } else {
          // Fallback pour les contextes non-sécurisés
          const textArea = document.createElement('textarea');
          textArea.value = text;
          textArea.style.position = 'fixed';
          textArea.style.left = '-999999px';
          textArea.style.top = '-999999px';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();

          const successful = document.execCommand('copy');
          document.body.removeChild(textArea);

          if (!successful) {
            throw new Error('Échec de la copie');
          }
        }

        setCopied(true);
        setError(null);
        onSuccess?.(text);

        // Reset après timeout
        setTimeout(() => {
          setCopied(false);
        }, timeout);

        return true;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Échec de la copie');
        setError(error);
        setCopied(false);
        onError?.(error);
        return false;
      }
    },
    [timeout, onSuccess, onError]
  );

  return { copied, copy, error };
}

/**
 * Hook pour lire depuis le presse-papier
 */
export interface UseClipboardReadResult {
  text: string | null;
  read: () => Promise<string | null>;
  error: Error | null;
  isSupported: boolean;
}

export function useClipboardRead(): UseClipboardReadResult {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const isSupported =
    typeof navigator !== 'undefined' &&
    'clipboard' in navigator &&
    'readText' in navigator.clipboard;

  const read = useCallback(async (): Promise<string | null> => {
    if (!isSupported) {
      const error = new Error('Clipboard API non supportée');
      setError(error);
      return null;
    }

    try {
      const clipboardText = await navigator.clipboard.readText();
      setText(clipboardText);
      setError(null);
      return clipboardText;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Échec de la lecture');
      setError(error);
      setText(null);
      return null;
    }
  }, [isSupported]);

  return { text, read, error, isSupported };
}
