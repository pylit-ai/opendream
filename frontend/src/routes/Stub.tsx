import { useLocation } from '@solidjs/router';

export function StubRoute(props: { name: string }) {
  const location = useLocation();
  return (
    <div class="flex h-[60vh] flex-col items-center justify-center gap-2 text-text-subtle">
      <div class="text-lg text-text">{props.name}</div>
      <div class="font-mono text-xs">Route: {location.pathname}</div>
      <div class="text-xs">Stub — implementation pending in later stories.</div>
    </div>
  );
}
