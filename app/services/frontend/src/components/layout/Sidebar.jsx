import { NavLink } from "react-router-dom"
import { Package, ClipboardList, MessageCircle, BarChart3 } from "lucide-react"

const navItems = [
  { to: "/", label: "Catálogo", icon: Package },
  { to: "/orders", label: "Órdenes", icon: ClipboardList },
  { to: "/faq", label: "FAQs", icon: MessageCircle },
  { to: "/dashboard", label: "Métricas", icon: BarChart3 },
]

export default function Sidebar() {
  return (
    <aside className="w-60 flex-shrink-0 flex flex-col" style={{ backgroundColor: "var(--sidebar)", color: "var(--sidebar-foreground)" }}>
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">🥜</span>
          <div>
            <h1 className="text-base font-bold text-white font-[var(--font-heading)]" style={{ fontFamily: "var(--font-heading)" }}>
              Tremenda Nuez
            </h1>
            <p className="text-[11px] text-white/40">Panel de administración</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors relative ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-white/60 hover:bg-white/5 hover:text-white/80"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r"
                    style={{ backgroundColor: "var(--sidebar-accent)" }}
                  />
                )}
                <item.icon className="w-4.5 h-4.5 flex-shrink-0" />
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Store info at bottom */}
      <div className="px-4 py-4 border-t border-white/10">
        <p className="text-xs font-medium text-white/70">Tremenda Nuez</p>
        <p className="text-[11px] text-white/30">Plan Básico</p>
      </div>
    </aside>
  )
}
