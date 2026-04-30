import type { JSX } from 'solid-js';
import { Chip } from './Chip';
import { memoryTypePresentation } from '~/lib/memoryPresentation';

export function MemoryTypeChip(props: { type?: string; class?: string }): JSX.Element {
  const presentation = () => memoryTypePresentation(props.type);
  return (
    <Chip variant={presentation().variant} class={props.class}>
      {presentation().label}
    </Chip>
  );
}
