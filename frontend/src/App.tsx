import { useEffect } from 'react';
import { HashRouter, Route, Routes, useLocation } from 'react-router-dom';
import { WalletProvider as AlgoKitWalletProvider } from '@txnlab/use-wallet-react';
import { walletManager } from './lib/walletConfig';
import { Nav } from './components/Nav';
import { Footer } from './components/Footer';
import { MeshBackground } from './components/MeshBackground';
import { RouteProgressBar } from './components/RouteProgressBar';
import { ToastProvider } from './lib/toast';
import { attachRippleListener } from './lib/ripple';

import { Home } from './pages/Home';
import { Verify } from './pages/Verify';
import { Result } from './pages/Result';
import { History } from './pages/History';
import { ReceiptVerify } from './pages/ReceiptVerify';
import { Anchoring } from './pages/Anchoring';
import { About } from './pages/About';
import { RecordDetail } from './pages/RecordDetail';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [pathname]);
  return null;
}

function AppShell() {
  return (
    <>
      
      <RouteProgressBar />
      <ScrollToTop />
      <MeshBackground />
      <div className="shell">
        <Nav />
        <main className="shell" style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="/result" element={<Result />} />
            <Route path="/history" element={<History />} />
            <Route path="/verify-receipt" element={<ReceiptVerify />} />
            <Route path="/anchoring" element={<Anchoring />} />
            <Route path="/record/:recordId" element={<RecordDetail />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </>
  );
}

function App() {
  useEffect(() => attachRippleListener(), []);

  return (
    <ToastProvider>
      <AlgoKitWalletProvider manager={walletManager}>
        <HashRouter>
          <AppShell />
        </HashRouter>
      </AlgoKitWalletProvider>
    </ToastProvider>
  );
}

export default App;

