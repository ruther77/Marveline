import { useCallback, useState, useRef } from 'react';
import { Upload, X, File, Image, FileText, FileSpreadsheet, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export interface FileWithPreview extends File {
  preview?: string;
}

export interface FileUploadProps {
  accept?: string;
  multiple?: boolean;
  maxSize?: number; // in bytes
  maxFiles?: number;
  value?: FileWithPreview[];
  onChange: (files: FileWithPreview[]) => void;
  onUpload?: (files: File[]) => Promise<void>;
  disabled?: boolean;
  error?: string;
  label?: string;
  hint?: string;
  className?: string;
}

const fileIcons: Record<string, typeof File> = {
  image: Image,
  pdf: FileText,
  spreadsheet: FileSpreadsheet,
  default: File,
};

function getFileIcon(file: File) {
  if (file.type.startsWith('image/')) return fileIcons.image;
  if (file.type === 'application/pdf') return fileIcons.pdf;
  if (file.type.includes('spreadsheet') || file.type.includes('excel') || file.name.endsWith('.csv')) {
    return fileIcons.spreadsheet;
  }
  return fileIcons.default;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function FileUpload({
  accept,
  multiple = false,
  maxSize = 10 * 1024 * 1024, // 10MB default
  maxFiles = 5,
  value = [],
  onChange,
  onUpload,
  disabled,
  error,
  label,
  hint,
  className,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList) return;

      const files = Array.from(fileList);
      const validFiles: FileWithPreview[] = [];

      for (const file of files) {
        // Check max files
        if (value.length + validFiles.length >= maxFiles) break;

        // Check size
        if (file.size > maxSize) {
          console.warn(`File ${file.name} exceeds max size`);
          continue;
        }

        // Add preview for images
        const fileWithPreview = file as FileWithPreview;
        if (file.type.startsWith('image/')) {
          fileWithPreview.preview = URL.createObjectURL(file);
        }

        validFiles.push(fileWithPreview);
      }

      const newFiles = multiple ? [...value, ...validFiles] : validFiles.slice(0, 1);
      onChange(newFiles);

      // Auto upload if handler provided
      if (onUpload && validFiles.length > 0) {
        setIsUploading(true);
        try {
          await onUpload(validFiles);
        } finally {
          setIsUploading(false);
        }
      }
    },
    [value, onChange, onUpload, maxFiles, maxSize, multiple]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (!disabled) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles, disabled]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const removeFile = (index: number) => {
    const file = value[index];
    if (file.preview) {
      URL.revokeObjectURL(file.preview);
    }
    const newFiles = value.filter((_, i) => i !== index);
    onChange(newFiles);
  };

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-dark-200 mb-1.5">
          {label}
        </label>
      )}

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors',
          isDragging
            ? 'border-primary-500 bg-primary-900/20'
            : error
            ? 'border-red-500 bg-red-900/10'
            : 'border-dark-600 hover:border-dark-500 hover:bg-dark-800/50',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => handleFiles(e.target.files)}
          disabled={disabled}
          className="sr-only"
        />

        <div className="flex flex-col items-center gap-3">
          {isUploading ? (
            <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
          ) : (
            <Upload className="w-10 h-10 text-dark-400" />
          )}
          <div>
            <p className="text-white font-medium">
              {isUploading ? 'Upload en cours...' : 'Glissez vos fichiers ici'}
            </p>
            <p className="text-sm text-dark-400 mt-1">
              ou <span className="text-primary-500">parcourez</span> votre ordinateur
            </p>
          </div>
          <p className="text-xs text-dark-500">
            Max {formatFileSize(maxSize)} par fichier
            {multiple && ` • ${maxFiles} fichiers max`}
          </p>
        </div>
      </div>

      {/* File list */}
      {value.length > 0 && (
        <div className="mt-4 space-y-2">
          {value.map((file, index) => {
            const FileIcon = getFileIcon(file);

            return (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center gap-3 p-3 bg-dark-800 rounded-lg border border-dark-700"
              >
                {file.preview ? (
                  <img
                    src={file.preview}
                    alt={file.name}
                    className="w-10 h-10 rounded object-cover"
                  />
                ) : (
                  <div className="w-10 h-10 bg-dark-700 rounded flex items-center justify-center">
                    <FileIcon className="w-5 h-5 text-dark-400" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{file.name}</p>
                  <p className="text-xs text-dark-400">{formatFileSize(file.size)}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
      {hint && !error && <p className="mt-2 text-sm text-dark-400">{hint}</p>}
    </div>
  );
}
