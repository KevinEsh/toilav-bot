import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import Catalog from "./pages/Catalog"

const navItems = [
  { to: "/", label: "Catálogo" },
  { to: "/orders", label: "Órdenes" },
  { to: "/faq", label: "FAQs" },
  { to: "/dashboard", label: "Métricas" },
]

function Placeholder({ title }) {
  return (
    <div className="flex items-center justify-center h-full">
      <h2 className="text-2xl text-gray-400">{title} — próximamente</h2>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        {/* Sidebar */}
        <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h1 className="text-lg font-bold text-gray-800">🥜 Tremenda Nuez</h1>
          </div>
          <nav className="flex-1 p-3 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-gray-900 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Catalog />} />
            <Route path="/orders" element={<Placeholder title="Órdenes" />} />
            <Route path="/faq" element={<Placeholder title="FAQs" />} />
            <Route path="/dashboard" element={<Placeholder title="Métricas" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}