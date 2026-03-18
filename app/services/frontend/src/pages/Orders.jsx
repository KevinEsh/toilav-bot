import { useState, useEffect } from "react"
import axios from "axios"
import { ChevronDown, ChevronRight, ClipboardList, Search } from "lucide-react"
import TopBar from "@/components/layout/TopBar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"

const API = "http://localhost:8000"

const statusConfig = {
  pending:          { label: "Pendiente",    className: "border-amber-300 text-amber-700 bg-amber-50" },
  confirmed:        { label: "Confirmada",   className: "border-blue-300 text-blue-700 bg-blue-50" },
  processing:       { label: "Procesando",   className: "border-purple-300 text-purple-700 bg-purple-50" },
  shipped:          { label: "Enviada",      className: "border-indigo-300 text-indigo-700 bg-indigo-50" },
  out_for_delivery: { label: "En camino",    className: "border-cyan-300 text-cyan-700 bg-cyan-50" },
  delivered:        { label: "Entregada",    className: "border-green-300 text-green-700 bg-green-50" },
  cancelled:        { label: "Cancelada",    className: "border-red-300 text-red-700 bg-red-50" },
  refunded:         { label: "Reembolsada",  className: "border-orange-300 text-orange-700 bg-orange-50" },
  failed:           { label: "Fallida",      className: "border-muted-foreground/30 text-muted-foreground bg-muted" },
}

const ALL_STATUSES = ["pending", "confirmed", "processing", "shipped", "out_for_delivery", "delivered", "cancelled", "refunded", "failed"]

function getStatusMeta(raw) {
  const key = raw?.toLowerCase()
  return statusConfig[key] || { label: raw || "—", className: "border-muted-foreground/30 text-muted-foreground bg-muted" }
}

function StatusBadge({ status }) {
  const meta = getStatusMeta(status)
  return (
    <Badge variant="outline" className={meta.className}>
      {meta.label}
    </Badge>
  )
}

function formatDate(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" })
}

function formatMoney(amount, currency = "MXN") {
  return `$${Number(amount || 0).toFixed(2)} ${currency}`
}

function TableSkeleton() {
  return (
    <div className="bg-card rounded-xl border border-border/50 shadow-sm overflow-hidden">
      <div className="bg-muted/50 px-4 py-3">
        <Skeleton className="h-3 w-full max-w-md" />
      </div>
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3.5 border-t border-border/50">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-4 w-24" />
        </div>
      ))}
    </div>
  )
}

function OrderDetail({ detail, loading }) {
  if (loading) {
    return (
      <div className="px-10 py-4 space-y-2">
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-3 w-full max-w-sm" />
        <Skeleton className="h-3 w-full max-w-sm" />
      </div>
    )
  }

  if (!detail) return null

  return (
    <div className="px-10 py-4 bg-muted/30">
      {detail.o_customer_notes && (
        <p className="text-xs text-muted-foreground italic mb-3">
          "{detail.o_customer_notes}"
        </p>
      )}

      {/* Items table */}
      <table className="w-full text-xs">
        <thead>
          <tr className="text-muted-foreground uppercase tracking-wider">
            <th className="text-left pb-2 font-medium">Producto</th>
            <th className="text-right pb-2 font-medium">Cant.</th>
            <th className="text-right pb-2 font-medium">Precio unit.</th>
            <th className="text-right pb-2 font-medium">Subtotal</th>
          </tr>
        </thead>
        <tbody>
          {detail.items.map((item) => (
            <tr key={item.oi_id} className="border-t border-border/50">
              <td className="py-1.5 text-foreground">{item.product_name}</td>
              <td className="py-1.5 text-right text-muted-foreground font-mono tabular-nums">{item.oi_units}</td>
              <td className="py-1.5 text-right text-muted-foreground font-mono tabular-nums">
                ${Number(item.oi_unit_price).toFixed(2)}
              </td>
              <td className="py-1.5 text-right font-medium text-foreground font-mono tabular-nums">
                ${(item.oi_units * item.oi_unit_price).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot className="text-xs">
          <tr className="border-t border-border/50">
            <td colSpan={3} className="pt-2 text-right text-muted-foreground">Subtotal</td>
            <td className="pt-2 text-right font-semibold text-foreground font-mono tabular-nums">
              ${Number(detail.o_subtotal).toFixed(2)}
            </td>
          </tr>
          {detail.o_shipping_amount > 0 && (
            <tr>
              <td colSpan={3} className="text-right text-muted-foreground">Envío</td>
              <td className="text-right font-mono tabular-nums">
                ${Number(detail.o_shipping_amount).toFixed(2)}
              </td>
            </tr>
          )}
          {detail.o_discount_amount > 0 && (
            <tr>
              <td colSpan={3} className="text-right text-green-600">Descuento</td>
              <td className="text-right text-green-600 font-mono tabular-nums">
                −${Number(detail.o_discount_amount).toFixed(2)}
              </td>
            </tr>
          )}
          <tr className="border-t border-border">
            <td colSpan={3} className="pt-2 text-right font-bold text-foreground">Total</td>
            <td className="pt-2 text-right font-bold text-foreground font-mono tabular-nums">
              {formatMoney(detail.o_total, detail.o_currency)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

function OrderRow({ order }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const toggle = async () => {
    if (!expanded && !detail) {
      setLoadingDetail(true)
      try {
        const res = await axios.get(`${API}/orders/${order.o_id}`)
        setDetail(res.data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoadingDetail(false)
      }
    }
    setExpanded((v) => !v)
  }

  return (
    <>
      <tr
        className="hover:bg-muted/30 cursor-pointer transition-colors"
        onClick={toggle}
      >
        <td className="px-4 py-3.5 text-muted-foreground w-8">
          {expanded
            ? <ChevronDown className="w-4 h-4" />
            : <ChevronRight className="w-4 h-4" />}
        </td>
        <td className="px-4 py-3.5 text-sm font-mono tabular-nums text-muted-foreground">
          #{order.o_id}
        </td>
        <td className="px-4 py-3.5">
          <p className="text-sm font-medium text-foreground">{order.customer_name || "—"}</p>
          {order.customer_phone && (
            <p className="text-xs text-muted-foreground">{order.customer_phone}</p>
          )}
        </td>
        <td className="px-4 py-3.5 text-sm text-muted-foreground">
          {formatDate(order.o_created_at)}
        </td>
        <td className="px-4 py-3.5 text-sm font-semibold text-foreground font-mono tabular-nums text-right">
          {formatMoney(order.o_total, order.o_currency)}
        </td>
        <td className="px-4 py-3.5">
          <StatusBadge status={order.o_status} />
        </td>
        <td className="px-4 py-3.5 text-xs text-muted-foreground capitalize">
          {order.o_payment_method?.replace(/_/g, " ").toLowerCase() || "—"}
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={7} className="p-0">
            <OrderDetail detail={detail} loading={loadingDetail} />
          </td>
        </tr>
      )}
    </>
  )
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeStatus, setActiveStatus] = useState("all")
  const [search, setSearch] = useState("")

  useEffect(() => {
    axios.get(`${API}/orders`)
      .then((r) => setOrders(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const statusCounts = orders.reduce((acc, o) => {
    const s = o.o_status?.toLowerCase()
    acc[s] = (acc[s] || 0) + 1
    return acc
  }, {})

  const filtered = orders.filter((o) => {
    const matchesStatus = activeStatus === "all" || o.o_status?.toLowerCase() === activeStatus
    const matchesSearch = !search.trim() ||
      o.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
      o.customer_phone?.includes(search) ||
      String(o.o_id).includes(search)
    return matchesStatus && matchesSearch
  })

  return (
    <div>
      <TopBar title="Órdenes">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Buscar cliente o #orden..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 w-56 h-9 text-sm"
          />
        </div>
        <Select value={activeStatus} onValueChange={setActiveStatus}>
          <SelectTrigger className="w-44 h-9 text-sm">
            <SelectValue placeholder="Filtrar estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas ({orders.length})</SelectItem>
            {ALL_STATUSES.filter((s) => statusCounts[s]).map((s) => (
              <SelectItem key={s} value={s}>
                {statusConfig[s]?.label} ({statusCounts[s]})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TopBar>

      {loading ? (
        <TableSkeleton />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <ClipboardList className="w-12 h-12 text-muted-foreground/40 mb-4" />
          <p className="text-base font-semibold text-foreground">
            {search || activeStatus !== "all" ? "Sin resultados" : "No hay órdenes aún"}
          </p>
          <p className="text-sm text-muted-foreground mt-1 max-w-xs">
            {search || activeStatus !== "all"
              ? "Intenta ajustar los filtros de búsqueda"
              : "Las órdenes de tus clientes aparecerán aquí"}
          </p>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border/50 shadow-sm overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-3 w-8 font-medium"></th>
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Cliente</th>
                <th className="px-4 py-3 font-medium">Fecha</th>
                <th className="px-4 py-3 font-medium text-right">Total</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 font-medium">Pago</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {filtered.map((o) => (
                <OrderRow key={o.o_id} order={o} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
