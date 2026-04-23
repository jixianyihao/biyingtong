export function ComingSoon({ label }: { label: string }) {
  return (
    <div className="p-8">
      <h1 className="text-2xl text-text-hi font-semibold mb-2">{label}</h1>
      <div className="text-text-dim text-sm">此页面在后续版本中从 v1 原型迁移过来。</div>
    </div>
  );
}
