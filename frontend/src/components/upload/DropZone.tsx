'use client';

import { useCallback, useState } from 'react';

interface DropZoneProps {
  onFileSelect: (file: File) => void | Promise<void>;
  isUploading: boolean;
  uploadProgress?: number;
}

const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']; // backend 5.1

const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export default function DropZone({ onFileSelect, isUploading, uploadProgress }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return 'Invalid file type. Please upload a PDF, JPEG or PNG file.';
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `File too large. Maximum size is ${MAX_SIZE_MB}MB.`;
    }
    return null;
  };

  const handleFile = useCallback((file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      return;
    }
    setError(null);
    setSelectedFile(file);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (selectedFile) {
      await onFileSelect(selectedFile);
      setSelectedFile(null);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    setError(null);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const getFileIcon = (type: string) => {
    if (type === 'application/pdf') {
      return (
        <svg
          className="w-8 h-8 text-red-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
      );
    }
    return (
      <svg
        className="w-8 h-8 text-blue-500"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
        />
      </svg>
    );
  };

  return (
    <div className="w-full">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative w-full min-h-[240px] rounded-2xl border-2 border-dashed
          transition-all duration-300 cursor-pointer
          flex flex-col items-center justify-center gap-4 p-8
          ${
            isDragging
              ? 'border-bright-green bg-bright-green/5 scale-[1.01]'
              : 'border-black/10 bg-white/40 hover:border-bright-green/50 hover:bg-white/60'
          }
          ${isUploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleInputChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />

        {/* Upload Icon */}
        <div
          className={`
          w-16 h-16 rounded-2xl flex items-center justify-center
          transition-all duration-300
          ${isDragging ? 'bg-bright-green/20' : 'bg-black/5'}
        `}
        >
          <svg
            className={`w-8 h-8 transition-colors ${isDragging ? 'text-bright-green' : 'text-light-text'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        </div>

        {/* Instructions */}
        <div className="text-center">
          <p className="font-sans text-[15px] text-dark-text font-medium">
            {isDragging ? 'Drop your file here' : 'Drag & drop your medical document'}
          </p>
          <p className="font-sans text-[13px] text-light-text mt-1">
            or <span className="text-bright-green font-medium">browse files</span>
          </p>
        </div>

        {/* Supported formats */}
        <div className="flex items-center gap-3 mt-2">
          <span className="px-2.5 py-1 rounded-full bg-black/5 font-sans text-[10px] font-medium uppercase tracking-wide text-light-text">
            PDF
          </span>
          <span className="px-2.5 py-1 rounded-full bg-black/5 font-sans text-[10px] font-medium uppercase tracking-wide text-light-text">
            JPEG
          </span>
          <span className="px-2.5 py-1 rounded-full bg-black/5 font-sans text-[10px] font-medium uppercase tracking-wide text-light-text">
            PNG
          </span>
          <span className="px-2.5 py-1 rounded-full bg-black/5 font-sans text-[10px] font-medium uppercase tracking-wide text-light-text">
            Max {MAX_SIZE_MB}MB
          </span>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <svg
            className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="font-sans text-[13px] text-red-700">{error}</p>
        </div>
      )}

      {/* Selected file preview */}
      {selectedFile && !error && (
        <div className="mt-4 rounded-xl border border-black/10 bg-white p-4">
          <div className="flex items-center gap-4">
            {getFileIcon(selectedFile.type)}
            <div className="flex-1 min-w-0">
              <p className="font-sans text-[14px] font-medium text-dark-text truncate">
                {selectedFile.name}
              </p>
              <p className="font-sans text-[12px] text-light-text mt-0.5">
                {formatFileSize(selectedFile.size)}
              </p>
            </div>
            {!isUploading && (
              <button
                onClick={handleClear}
                className="p-2 rounded-lg hover:bg-black/5 transition-colors"
              >
                <svg
                  className="w-5 h-5 text-light-text"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Upload progress */}
          {isUploading && uploadProgress !== undefined && (
            <div className="mt-3">
              <div className="h-1.5 w-full rounded-full bg-black/5 overflow-hidden">
                <div
                  className="h-full bg-bright-green transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="font-sans text-[11px] text-light-text mt-1.5 text-center">
                Uploading... {uploadProgress}%
              </p>
            </div>
          )}

          {/* Upload button */}
          {!isUploading && (
            <button
              onClick={handleUpload}
              className="mt-4 w-full h-11 rounded-full bg-[#162a1c] font-sans text-[14px] font-medium text-cream transition-all duration-300 hover:-translate-y-0.5 hover:bg-[#1d3a26] hover:shadow-lg active:translate-y-0 flex items-center justify-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                />
              </svg>
              Upload Document
            </button>
          )}
        </div>
      )}
    </div>
  );
}
