import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
  type UIEvent,
} from "react";

function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

interface AnimatedItemProps {
  children: ReactNode;
  index: number;
  selected: boolean;
  rootRef: RefObject<HTMLDivElement | null>;
  onMouseEnter?: () => void;
  onClick?: () => void;
  itemClassName?: string;
}

function AnimatedItem({
  children,
  index,
  selected,
  rootRef,
  onMouseEnter,
  onClick,
  itemClassName,
}: AnimatedItemProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) {
          return;
        }
        setInView(entry.isIntersecting && entry.intersectionRatio >= 0.45);
      },
      {
        root: rootRef.current,
        threshold: [0, 0.45, 0.9],
      },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [rootRef]);

  return (
    <div
      ref={ref}
      role="option"
      aria-selected={selected}
      data-list-index={index}
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      className={cn(
        "animated-list-item",
        inView && "in-view",
        selected && "selected",
        itemClassName,
      )}
      style={{ transitionDelay: `${Math.min(index * 20, 180)}ms` }}
    >
      {children}
    </div>
  );
}

export interface AnimatedListProps {
  items?: string[];
  onItemSelect?: (item: string, index: number) => void;
  showGradients?: boolean;
  enableArrowNavigation?: boolean;
  className?: string;
  itemClassName?: string;
  displayScrollbar?: boolean;
  initialSelectedIndex?: number;
}

export function AnimatedList({
  items = [],
  onItemSelect,
  showGradients = true,
  enableArrowNavigation = true,
  className,
  itemClassName,
  displayScrollbar = true,
  initialSelectedIndex = -1,
}: AnimatedListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(initialSelectedIndex);
  const [topGradientOpacity, setTopGradientOpacity] = useState<number>(0);
  const [bottomGradientOpacity, setBottomGradientOpacity] = useState<number>(1);

  const updateGradientOpacity = useCallback((scrollTop: number, scrollHeight: number, clientHeight: number) => {
    setTopGradientOpacity(Math.min(scrollTop / 44, 1));
    const bottomDistance = Math.max(scrollHeight - (scrollTop + clientHeight), 0);
    const bottomOpacity = scrollHeight <= clientHeight ? 0 : Math.min(bottomDistance / 44, 1);
    setBottomGradientOpacity(bottomOpacity);
  }, []);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    const target = event.target as HTMLDivElement;
    updateGradientOpacity(target.scrollTop, target.scrollHeight, target.clientHeight);
  };

  const selectItem = useCallback(
    (index: number) => {
      if (index < 0 || index >= items.length) {
        return;
      }

      setSelectedIndex(index);
      const item = items[index];
      if (item && onItemSelect) {
        onItemSelect(item, index);
      }
    },
    [items, onItemSelect],
  );

  useEffect(() => {
    const node = listRef.current;
    if (!node) {
      return;
    }

    updateGradientOpacity(node.scrollTop, node.scrollHeight, node.clientHeight);
  }, [items.length, updateGradientOpacity]);

  useEffect(() => {
    if (selectedIndex < 0) {
      return;
    }

    const container = listRef.current;
    if (!container) {
      return;
    }

    const selectedItem = container.querySelector(`[data-list-index=\"${selectedIndex}\"]`) as HTMLElement | null;
    if (!selectedItem) {
      return;
    }

    const margin = 42;
    const containerTop = container.scrollTop;
    const containerHeight = container.clientHeight;
    const itemTop = selectedItem.offsetTop;
    const itemBottom = itemTop + selectedItem.offsetHeight;

    if (itemTop < containerTop + margin) {
      container.scrollTo({ top: Math.max(itemTop - margin, 0), behavior: "smooth" });
      return;
    }

    if (itemBottom > containerTop + containerHeight - margin) {
      container.scrollTo({ top: itemBottom - containerHeight + margin, behavior: "smooth" });
    }
  }, [selectedIndex]);

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!enableArrowNavigation || items.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((previous) => Math.min(previous + 1, items.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((previous) => Math.max(previous - 1, 0));
      return;
    }

    if (event.key === "Enter" && selectedIndex >= 0) {
      event.preventDefault();
      selectItem(selectedIndex);
    }
  };

  return (
    <div className={cn("animated-list-root", className)}>
      <div
        ref={listRef}
        role="listbox"
        tabIndex={enableArrowNavigation ? 0 : -1}
        onKeyDown={handleKeyDown}
        onScroll={handleScroll}
        className={cn("animated-list-scroll", displayScrollbar ? "show-scrollbar" : "hide-scrollbar")}
      >
        {items.map((item, index) => (
          <AnimatedItem
            key={`${item}-${index}`}
            index={index}
            selected={selectedIndex === index}
            rootRef={listRef}
            itemClassName={itemClassName}
            onMouseEnter={() => setSelectedIndex(index)}
            onClick={() => selectItem(index)}
          >
            <p className="animated-list-text">{item}</p>
          </AnimatedItem>
        ))}
      </div>

      {showGradients ? (
        <>
          <div className="animated-list-gradient top" style={{ opacity: topGradientOpacity }} />
          <div className="animated-list-gradient bottom" style={{ opacity: bottomGradientOpacity }} />
        </>
      ) : null}
    </div>
  );
}

export default AnimatedList;
