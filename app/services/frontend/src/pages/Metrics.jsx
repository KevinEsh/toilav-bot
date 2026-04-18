import { useState, useEffect } from "react"
import axios from "axios"
import { ShoppingBag, DollarSign, Users, TrendingUp, BarChart3, AlertCircle } from "lucide-react"
import TopBar from "@/components/layout/TopBar"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

const API = "http://localhost:8000"

const STATUS_LABEL = {
  pending: "Pendiente", confirmed: "Confirmada", processing: "Procesando",
  shipped: "Enviada", out_for_delivery: "En camino", delivered: "Entregada",
  cancelled: "Cancelada", refunded: "Reembolsada", failed: "Fallida",
  PENDING: "Pendiente", CONFIRMED: "Confirmada", PROCESSING: "Procesando",
  SHIPPED: "Enviada", DELIVERED: "Entregada", CANCELLED: "Cancelada",
  REFUNDED: "Reembolsada", FAILED: "Fallida", CUSTOMER_REVIEWING: "En revisión"
}

const STATUS_COLOR = {
  pending: "bg-amber-400", confirmed: "bg-blue-400", processing: "bg-purple-400",
  shipped: "bg-indigo-400", out_for_delivery: "bg-cyan-400", delivered: "bg-green-500",
  cancelled: "bg-red-400", refunded: "bg-orange-400", failed: "bg-muted-foreground/40",
  PENDING: "bg-amber-400", CONFIRMED: "bg-blue-400", PROCESSING: "bg-purple-400",
  SHIPPED: "bg-indigo-400", DELIVERED: "bg-green-500", CANCELLED: "bg-red-400",
  REFUNDED: "bg-orange-400", FAILED: "bg-muted-foreground/40", CUSTOMER_REVIEWING: "bg-yellow-400"
}

/* ── KPI Card ── */
function KpiCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <Card className="border border-border/50 shadow-sm hover:shadow-md transition-shadow">
      <CardContent className="p-5 flex items-center gap-4">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${accent}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold text-foreground leading-none font-mono tabular-nums">
            {value}
          </p>
          <p className="text-xs text-muted-foreground mt-1 truncate">{label}</p>
          {sub && <p className="text-[11px] text-muted-foreground/60 mt-0.5">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

function KpiSkeleton() {
  return (
    <Card className="border border-border/50 shadow-sm">
      <CardContent className="p-5 flex items-center gap-4">
        <Skeleton className="w-11 h-11 rounded-xl flex-shrink-0" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-3 w-28" />
        </div>
      </CardContent>
    </Card>
  )
}

/* ── Horizontal Bar ── */
function HBar({ label, value, max, color = "bg-primary" }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-foreground w-36 truncate flex-shrink-0">{label}</span>
      <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-foreground w-8 text-right flex-shrink-0 font-mono tabular-nums">
        {value}
      </span>
    </div>
  )
}

/* ── Revenue Bar Chart ── */
const CHART_H = 160

function formatShortDate(dateStr) {
  if (!dateStr) return ""
  const [, m, d] = dateStr.split("-")
  const months = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
  return `${parseInt(d)} ${months[parseInt(m)]}`
}

function RevenueChart({ data }) {
  if (!data || data.length === 0) {
    return <p className="text-xs text-muted-foreground">Sin datos de ingresos</p>
  }

  const max = Math.max(...data.map((d) => d.revenue), 1)
  // Show ~4 Y-axis reference lines
  const step = Math.ceil(max / 4 / 100) * 100
  const yLines = []
  for (let v = step; v < max; v += step) yLines.push(v)

  return (
    <div className="flex gap-2">
      {/* Y axis labels */}
      <div className="flex flex-col justify-between pb-7 pt-0.5 text-right" style={{ height: CHART_H + 28 }}>
        <span className="text-[10px] text-muted-foreground/60 font-mono">
          ${max.toLocaleString("es-MX", { maximumFractionDigits: 0 })}
        </span>
        {yLines.reverse().map((v) => (
          <span key={v} className="text-[10px] text-muted-foreground/60 font-mono">
            ${v.toLocaleString("es-MX", { maximumFractionDigits: 0 })}
          </span>
        ))}
        <span className="text-[10px] text-muted-foreground/60 font-mono">$0</span>
      </div>

      {/* Bars + X axis */}
      <div className="flex-1 min-w-0">
        {/* Grid lines + bars */}
        <div className="relative border-b border-border/50" style={{ height: CHART_H }}>
          {/* Horizontal grid lines */}
          {[0.25, 0.5, 0.75].map((pct) => (
            <div
              key={pct}
              className="absolute left-0 right-0 border-t border-border/30"
              style={{ bottom: `${pct * 100}%` }}
            />
          ))}

          {/* Bars */}
          <div className="flex items-end gap-1 h-full px-0.5">
            {data.map((d) => {
              const h = Math.max(2, Math.round((d.revenue / max) * CHART_H))
              return (
                <div key={d.date} className="flex-1 relative group">
                  <div
                    className="w-full bg-primary/70 rounded-t hover:bg-primary transition-colors"
                    style={{ height: h }}
                  />
                  {/* Tooltip */}
                  <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-foreground text-background text-[10px] font-mono px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10 shadow-lg">
                    ${d.revenue.toLocaleString("es-MX", { maximumFractionDigits: 0 })}
                    <span className="text-background/60 ml-1">— {formatShortDate(d.date)}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* X axis labels */}
        <div className="flex gap-1 px-0.5 mt-1.5">
          {data.map((d, i) => {
            // Show label every ~N bars to avoid crowding
            const showEvery = data.length > 14 ? 3 : data.length > 7 ? 2 : 1
            const show = i % showEvery === 0 || i === data.length - 1
            return (
              <div key={d.date} className="flex-1 text-center">
                {show && (
                  <span className="text-[10px] text-muted-foreground/60">
                    {formatShortDate(d.date)}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/* ── Main ── */
export default function Metrics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const fetchMetrics = () => {
    setLoading(true)
    setError(false)
    axios.get(`${API}/metrics`)
      .then((r) => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchMetrics() }, [])

  if (loading) {
    return (
      <div>
        <TopBar title="Métricas" />
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => <KpiSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          {[1, 2].map((i) => (
            <Card key={i} className="border border-border/50 shadow-sm">
              <CardContent className="p-5 space-y-3">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-2 w-3/4" />
                <Skeleton className="h-2 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="border border-border/50 shadow-sm">
          <CardContent className="p-5">
            <Skeleton className="h-4 w-40 mb-4" />
            <Skeleton className="h-36 w-full rounded" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div>
        <TopBar title="Métricas" />
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <AlertCircle className="w-12 h-12 text-destructive/50 mb-4" />
          <p className="text-base font-semibold text-foreground">Error cargando métricas</p>
          <p className="text-sm text-muted-foreground mt-1">No se pudo conectar con el servidor</p>
          <Button variant="outline" onClick={fetchMetrics} className="mt-5">
            Reintentar
          </Button>
        </div>
      </div>
    )
  }

  const maxStatus = Math.max(...Object.values(data.orders_by_status), 1)
  const maxProduct = data.top_products.length > 0
    ? Math.max(...data.top_products.map((p) => p.units_sold), 1)
    : 1

  const avgTicket = data.total_orders > 0
    ? (data.total_revenue / data.total_orders)
    : 0

  const completedCount = Object.entries(data.orders_by_status)
    .filter(([k]) => k.toLowerCase() === "delivered")
    .reduce((sum, [, v]) => sum + v, 0)
  const completionRate = data.total_orders > 0
    ? Math.round((completedCount / data.total_orders) * 100)
    : 0

  return (
    <div>
      <TopBar title="Métricas" />

      {/* KPI row */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <KpiCard
          icon={ShoppingBag}
          label="Órdenes totales"
          value={data.total_orders}
          accent="bg-primary"
        />
        <KpiCard
          icon={DollarSign}
          label="Ingresos totales"
          value={`$${data.total_revenue.toLocaleString("es-MX", { maximumFractionDigits: 0 })}`}
          sub="MXN"
          accent="bg-green-600"
        />
        <KpiCard
          icon={TrendingUp}
          label="Ticket promedio"
          value={`$${avgTicket.toLocaleString("es-MX", { maximumFractionDigits: 0 })}`}
          sub={`${completionRate}% completadas`}
          accent="bg-purple-600"
        />
        <KpiCard
          icon={Users}
          label="Clientes activos"
          value={data.active_customers}
          accent="bg-blue-600"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Orders by status — donut placeholder as horizontal bars */}
        <Card className="border border-border/50 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-semibold">Órdenes por estado</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(data.orders_by_status).length === 0 ? (
              <p className="text-xs text-muted-foreground">Sin órdenes registradas</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(data.orders_by_status)
                  .sort((a, b) => b[1] - a[1])
                  .map(([status, count]) => (
                    <HBar
                      key={status}
                      label={STATUS_LABEL[status] || status}
                      value={count}
                      max={maxStatus}
                      color={STATUS_COLOR[status] || "bg-muted-foreground/40"}
                    />
                  ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top products */}
        <Card className="border border-border/50 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-semibold">Productos más vendidos</CardTitle>
          </CardHeader>
          <CardContent>
            {data.top_products.length === 0 ? (
              <div className="flex flex-col items-center py-6 text-center">
                <BarChart3 className="w-8 h-8 text-muted-foreground/40 mb-2" />
                <p className="text-xs text-muted-foreground">Sin datos de ventas aún</p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.top_products.map((p, i) => (
                  <HBar
                    key={i}
                    label={p.name}
                    value={p.units_sold}
                    max={maxProduct}
                    color="bg-primary"
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Revenue over time */}
      <Card className="border border-border/50 shadow-sm hover:shadow-md transition-shadow">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg font-semibold">Ingresos por día</CardTitle>
        </CardHeader>
        <CardContent>
          <RevenueChart data={data.daily_revenue} />
        </CardContent>
      </Card>
    </div>
  )
}
