export default function TopBar({ title, children }) {
  return (
    <div className="flex items-center justify-between mb-6">
      <h1
        className="text-2xl font-bold text-foreground"
        style={{ fontFamily: "var(--font-heading)" }}
      >
        {title}
      </h1>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}
