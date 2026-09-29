import type { Metadata } from 'next';
import './globals.css';
import SmoothScrollProvider from '../src/components/SmoothScrollProvider';
import PageLoader from '../src/components/PageLoader';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'Etheria - Interactive Health AI',
  description: 'An AI-based interactive symptom assessment and health recommendation system.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <PageLoader />
          <SmoothScrollProvider>{children}</SmoothScrollProvider>
        </Providers>
      </body>
    </html>
  );
}
