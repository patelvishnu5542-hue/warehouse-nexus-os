import React from 'react';

const WarehouseGrid = ({ state }) => {
  const { grid_size, inventory, workers } = state;
  const width = grid_size[0];
  const height = grid_size[1];

  // Create a 2D mapping for items, but hide those currently held by workers
  const heldItems = new Set(workers.flatMap(w => w.items_held));
  const itemMap = {};
  Object.entries(inventory).forEach(([id, pos]) => {
    if (heldItems.has(id)) return; // Don't show picked items
    const key = `${pos[0]},${pos[1]}`;
    if (!itemMap[key]) itemMap[key] = [];
    itemMap[key].push(id);
  });

  const renderCells = () => {
    let cells = [];
    for (let y = height - 1; y >= 0; y--) {
      for (let x = 0; x < width; x++) {
        const key = `${x},${y}`;
        const hasItem = itemMap[key];
        cells.push(
          <div key={key} className={`cell ${hasItem ? 'item' : ''}`}>
            {/* Optional: Render small label or rack style */}
          </div>
        );
      }
    }
    return cells;
  };

  return (
    <div 
      className="warehouse-grid" 
      style={{ 
        gridTemplateColumns: `repeat(${width}, 40px)`,
        gridTemplateRows: `repeat(${height}, 40px)`,
        position: 'relative'
      }}
    >
      {renderCells()}
      
      {/* Render Robots (Workers) with Absolute Positioning for smooth movement */}
      {workers.map((worker) => {
        const [x, y] = worker.position;
        const top = (height - 1 - y) * 42; 
        const left = x * 42;
        
        return (
          <div 
            key={worker.id}
            className={`robot ${worker.status === 'busy' ? 'busy' : ''}`}
            style={{ 
              top: `${top + 8}px`, 
              left: `${left + 8}px`,
              transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center'
            }}
          >
            <span style={{ fontSize: '14px' }}>🤖</span>
            <span style={{ fontSize: '8px', marginTop: '-4px', opacity: 0.8 }}>W{worker.id}</span>
            {worker.load > 0 && (
              <div 
                style={{
                  position: 'absolute',
                  top: '-8px',
                  right: '-8px',
                  fontSize: '10px'
                }}
              >
                📦
              </div>
            )}
          </div>
        );
      })}

      {/* Delivery Zone (0,0) */}
      <div 
        style={{
          position: 'absolute',
          bottom: '1px',
          left: '1px',
          width: '38px',
          height: '38px',
          border: '2px solid var(--secondary)',
          borderRadius: '8px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          fontSize: '18px',
          background: 'rgba(6, 182, 212, 0.1)',
          boxShadow: 'inset 0 0 10px rgba(6, 182, 212, 0.2)'
        }}
      >
        🏁
      </div>
    </div>
  );
};

export default WarehouseGrid;
