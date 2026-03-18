import { BrowserRouter, Routes, Route } from "react-router-dom"
import AppShell from "./components/layout/AppShell"
import Catalog from "./pages/Catalog"
import Orders from "./pages/Orders"
import FAQ from "./pages/FAQ"
import Metrics from "./pages/Metrics"

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/dashboard" element={<Metrics />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}
