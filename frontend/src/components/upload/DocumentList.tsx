'use client';

import { useEffect } from 'react';
import type { DocumentInfo } from '../../lib/api';

interface DocumentListProps {
  documents: DocumentInfo[];
  onDelete: (documentId: string) => void;
  onDownload: (doc: DocumentInfo) => void;
  onRefresh: () => void;
  isDeleting?: string | null;
}

export default function DocumentList({
  documents,
  onDelete,
  onDownload,
  onRefresh,
  isDeleting,
}: DocumentListProps) {
  const hasProcessing = documents.some(
    (doc) => doc.status === 'pending' || doc.status === 'processing'
  );

  // Poll for status updates while any document is being ingested
  useEffect(() => {
    if (!hasProcessing) return;
    const timer = setInterval(onRefresh, 3000);
    return () => clearInterval(timer);
  }, [hasProcessing, onRefresh]);

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (status: DocumentInfo['status']) => {
    switch (status) {
      case 'pending':
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            <span className="font-sans text-[11px] font-medium text-amber-700 uppercase tracking-wide">
              Processing
            </span>
          </span>
        );
      case 'done':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-50 border border-green-200">
            <svg
              className="w-3 h-3 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <span className="font-sans text-[11px] font-medium text-green-700 uppercase tracking-wide">
              Ready
            </span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 border border-red-200">
            <svg
              className="w-3 h-3 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span className="font-sans text-[11px] font-medium text-red-700 uppercase tracking-wide">
              Failed
            </span>
          </span>
        );
    }
  };

  const getFileIcon = (fileType: string) => {
    if (fileType === 'pdf') {
      return (
        <div className="w-10 h-10 rounded-xl bg-red-50 border border-red-100 flex items-center justify-center">
          <svg
            className="w-5 h-5 text-red-500"
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
        </div>
      );
    }
    return (
      <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center">
        <svg
          className="w-5 h-5 text-blue-500"
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
      </div>
    );
  };

  if (documents.length === 0) {
    return (
      <div className="rounded-2xl border border-black/10 bg-white/60 p-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-black/5 flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-7 h-7 text-light-text"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
            />
          </svg>
        </div>
        <p className="font-sans text-[15px] text-dark-text font-medium">No documents yet</p>
        <p className="font-sans text-[13px] text-light-text mt-1">
          Upload your medical records to get personalized insights
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[0.15em] text-light-text">
          Your Documents
        </h3>
        <span className="font-sans text-[12px] text-light-text">
          {documents.length} file{documents.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="space-y-2">
        {documents.map((doc) => (
          <div
            key={doc.documentId}
            className="group rounded-xl border border-black/10 bg-white p-4 transition-all duration-200 hover:border-black/20 hover:shadow-sm"
          >
            <div className="flex items-center gap-4">
              {getFileIcon(doc.fileType)}

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <p className="font-sans text-[14px] font-medium text-dark-text truncate">
                    {doc.filename}
                  </p>
                  {getStatusBadge(doc.status)}
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <p className="font-sans text-[12px] text-light-text">
                    {formatDate(doc.uploadedAt)}
                  </p>
                  {doc.pageCount && (
                    <>
                      <span className="text-light-text/40">•</span>
                      <p className="font-sans text-[12px] text-light-text">
                        {doc.pageCount} page{doc.pageCount !== 1 ? 's' : ''}
                      </p>
                    </>
                  )}
                </div>
                {doc.status === 'done' && doc.summary && (
                  <p className="font-sans text-[12px] text-light-text mt-1 line-clamp-2">
                    {doc.docType ? `${doc.docType.replace(/_/g, ' ')} · ` : ''}
                    {doc.summary}
                  </p>
                )}
              </div>

              {/* Download button */}
              <button
                onClick={() => onDownload(doc)}
                className="p-2 rounded-lg text-light-text/60 hover:text-dark-text hover:bg-black/5 transition-colors opacity-0 group-hover:opacity-100"
                title="Download document"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
              </button>

              {/* Delete button */}
              <button
                onClick={() => onDelete(doc.documentId)}
                disabled={isDeleting === doc.documentId}
                className="p-2 rounded-lg text-light-text/60 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                title="Delete document"
              >
                {isDeleting === doc.documentId ? (
                  <span className="w-5 h-5 flex items-center justify-center">
                    <span className="w-4 h-4 rounded-full border-2 border-light-text/20 border-t-light-text animate-spin" />
                  </span>
                ) : (
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                    />
                  </svg>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
