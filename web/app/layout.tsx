import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'FleetVerse — warehouse intelligence', description: 'A deterministic autonomous warehouse digital twin, incident replay and what-if laboratory.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
