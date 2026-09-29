'use client';

import { useAuth, useClerk } from '../../../src/lib/auth';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import DropZone from '../../../src/components/upload/DropZone';
import DocumentList from '../../../src/components/upload/DocumentList';
import {
  uploadDocument,
  fetchDocuments,
  deleteDocument,
  downloadDocument,
  errorMessage,
  type DocumentInfo,
} from '../../../src/lib/api';

export default function UploadPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const { signOut } = useClerk();
  const router = useRouter();

  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Redirect if not signed in
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push('/sign-in');
    }
  }, [isLoaded, isSignedIn, router]);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  }, []);

  // Load documents on mount (state is set in the promise callback, not the effect body)
  useEffect(() => {
    if (!isSignedIn) return;
    let cancelled = false;
    fetchDocuments()
      .then((docs) => !cancelled && setDocuments(docs))
      .catch((err) => console.error('Failed to load documents:', err));
    return () => {
      cancelled = true;
    };
  }, [isSignedIn]);

  const handleFileSelect = async (file: File) => {
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);
    setSuccess(null);

    // Simulate progress (actual progress would require XHR/fetch with progress events)
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => Math.min(prev + 10, 90));
    }, 200);

    try {
      const result = await uploadDocument(file);
      clearInterval(progressInterval);
      setUploadProgress(100);

      // Reload the list; DocumentList polls while ingestion runs.
      await loadDocuments();

      setSuccess(`"${result.filename}" uploaded. It is being processed now.`);

      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      clearInterval(progressInterval);
      setError(errorMessage(err, 'Upload failed. Please try again.'));
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (documentId: string) => {
    setIsDeleting(documentId);
    setError(null);

    try {
      await deleteDocument(documentId);
      setDocuments((prev) => prev.filter((doc) => doc.documentId !== documentId));
    } catch (err) {
      setError(errorMessage(err, 'Failed to delete document.'));
    } finally {
      setIsDeleting(null);
    }
  };

  const handleDownload = async (doc: DocumentInfo) => {
    setError(null);
    try {
      await downloadDocument(doc.documentId, doc.filename);
    } catch (err) {
      setError(errorMessage(err, 'Failed to download document.'));
    }
  };

  const handleSignOut = async () => {
    await signOut({ redirectUrl: '/' });
  };

  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-[#f5f2ec] flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-bright-green/20 border-t-bright-green animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f5f2ec]">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#f5f2ec]/90 backdrop-blur-md border-b border-black/5">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-3">
            <Image
              src="/logo-light.png"
              alt="Etheria"
              width={100}
              height={30}
              style={{
                height: '26px',
                width: 'auto',
                filter: 'invert(1) sepia(1) saturate(0) brightness(0.2)',
              }}
              priority
            />
          </Link>

          <nav className="flex items-center gap-6">
            <Link
              href="/dashboard"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Chat
            </Link>
            <Link
              href="/dashboard/upload"
              className="font-sans text-[13px] text-dark-text font-medium"
            >
              Documents
            </Link>
            <Link
              href="/dashboard/history"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              History
            </Link>
            <Link
              href="/dashboard/account"
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Account
            </Link>
            <button
              onClick={handleSignOut}
              className="font-sans text-[13px] text-light-text hover:text-dark-text transition-colors"
            >
              Sign Out
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-6 py-12">
        {/* Page Header */}
        <div className="mb-10">
          <p className="font-sans text-[10px] font-semibold tracking-[0.22em] uppercase text-bright-green mb-2">
            Documents
          </p>
          <h1 className="font-flare text-[clamp(32px,5vw,48px)] font-normal text-dark-text leading-[0.95] tracking-[-0.02em]">
            Upload your
            <br />
            <span className="italic">medical records</span>
          </h1>
          <p className="mt-4 font-sans text-[14px] text-light-text leading-[1.6] max-w-lg">
            Upload lab reports, prescriptions or discharge summaries (PDF, or a scanned image).
            Etheria reads them so you can ask about your own results in chat. Use synthetic reports
            only: this is a demo, not a clinical service.
          </p>
        </div>

        {/* Success message */}
        {success && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
            <svg
              className="w-5 h-5 text-green-600 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="font-sans text-[13px] text-green-700">{success}</p>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <svg
              className="w-5 h-5 text-red-500 shrink-0"
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
            <button
              onClick={() => setError(null)}
              className="ml-auto p-1 hover:bg-red-100 rounded transition-colors"
            >
              <svg
                className="w-4 h-4 text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Upload Section */}
        <section className="mb-12">
          <DropZone
            onFileSelect={handleFileSelect}
            isUploading={isUploading}
            uploadProgress={uploadProgress}
          />
        </section>

        {/* Documents List */}
        <section>
          <DocumentList
            documents={documents}
            onDelete={handleDelete}
            onDownload={handleDownload}
            onRefresh={loadDocuments}
            isDeleting={isDeleting}
          />
        </section>

        {/* Privacy Note */}
        <div className="mt-12 p-4 rounded-xl bg-black/[0.03] border border-black/5">
          <div className="flex items-start gap-3">
            <svg
              className="w-5 h-5 text-light-text shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
              />
            </svg>
            <div>
              <p className="font-sans text-[13px] text-dark-text font-medium">
                Your privacy is protected
              </p>
              <p className="font-sans text-[12px] text-light-text mt-1 leading-[1.6]">
                Files are encrypted at rest (AES-256-GCM). Aadhaar and phone numbers are masked
                before any text reaches the AI model (DeepSeek, servers outside India).
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
