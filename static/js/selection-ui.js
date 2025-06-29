// 選択UI管理クラス
class SelectionUI {
    constructor(options = {}) {
        this.isSelectionMode = false;
        this.selectedItems = new Set();
        this.options = {
            onCopy: null,
            onDelete: null,
            onEdit: null,
            onCancel: null,
            getItemId: (element) => element.dataset.id || element.getAttribute('data-id'),
            ...options
        };
        
        this.init();
    }
    
    init() {
        this.createUI();
        this.bindEvents();
    }
    
    createUI() {
        // 選択ボタンコンテナ
        this.selectFabContainer = document.createElement('div');
        this.selectFabContainer.className = 'selection-fab-container';
        this.selectFabContainer.id = 'selectionFabContainer';
        this.selectFabContainer.style.display = 'none';
        
        // 選択ボタン
        this.selectFab = document.createElement('button');
        this.selectFab.className = 'selection-fab';
        this.selectFab.innerHTML = '<i class="material-icons">check_circle</i>';
        this.selectFab.id = 'selectFab';
        
        // キャンセルボタン
        this.cancelFab = document.createElement('button');
        this.cancelFab.className = 'selection-fab cancel';
        this.cancelFab.innerHTML = '<i class="material-icons">close</i>';
        this.cancelFab.id = 'cancelFab';
        this.cancelFab.style.display = 'none';
        
        // 右下ボタングループ
        this.fabGroup = document.createElement('div');
        this.fabGroup.className = 'selection-fab-group';
        this.fabGroup.style.display = 'none';
        
        // 編集ボタン（一番上）
        this.editFab = document.createElement('button');
        this.editFab.className = 'selection-fab edit';
        this.editFab.innerHTML = '<i class="material-icons">edit</i>';
        this.editFab.id = 'editFab';
        
        // コピーボタン
        this.copyFab = document.createElement('button');
        this.copyFab.className = 'selection-fab copy';
        this.copyFab.innerHTML = '<i class="material-icons">content_copy</i>';
        this.copyFab.id = 'copyFab';
        
        // 削除ボタン
        this.deleteFab = document.createElement('button');
        this.deleteFab.className = 'selection-fab delete';
        this.deleteFab.innerHTML = '<i class="material-icons">delete</i>';
        this.deleteFab.id = 'deleteFab';
        
        // 選択カウント
        this.selectionCount = document.createElement('div');
        this.selectionCount.className = 'selection-count';
        this.selectionCount.id = 'selectionCount';
        
        // DOMに追加
        this.selectFabContainer.appendChild(this.selectFab);
        this.selectFabContainer.appendChild(this.cancelFab);
        
        // 編集ボタンを一番上に配置
        this.fabGroup.appendChild(this.editFab);
        this.fabGroup.appendChild(this.copyFab);
        this.fabGroup.appendChild(this.deleteFab);
        
        document.body.appendChild(this.selectFabContainer);
        document.body.appendChild(this.fabGroup);
        document.body.appendChild(this.selectionCount);
    }
    
    bindEvents() {
        // 選択ボタン
        this.selectFab.addEventListener('click', () => this.enterSelectionMode());
        
        // キャンセルボタン
        this.cancelFab.addEventListener('click', () => this.exitSelectionMode());
        
        // アクションボタン
        this.copyFab.addEventListener('click', () => this.executeCopy());
        this.deleteFab.addEventListener('click', () => this.executeDelete());
        this.editFab.addEventListener('click', () => this.executeEdit());
        
        // ESCキーで選択モードを終了
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isSelectionMode) {
                this.exitSelectionMode();
            }
        });
    }
    
    enterSelectionMode() {
        this.isSelectionMode = true;
        document.body.classList.add('selection-mode');
        
        // ボタンの表示切り替え
        this.selectFab.style.display = 'none';
        this.cancelFab.style.display = 'flex';
        this.fabGroup.style.display = 'flex';
        
        // 選択可能なアイテムにチェックボックスを追加
        this.addCheckboxesToItems();
        
        // 選択カウントを表示
        this.updateSelectionCount();
    }
    
    exitSelectionMode() {
        this.isSelectionMode = false;
        this.selectedItems.clear();
        document.body.classList.remove('selection-mode');
        
        // ボタンの表示切り替え
        this.selectFab.style.display = 'flex';
        this.cancelFab.style.display = 'none';
        this.fabGroup.style.display = 'none';
        
        // チェックボックスを削除
        this.removeCheckboxesFromItems();
        
        // 選択カウントを非表示
        this.selectionCount.style.display = 'none';
        
        // コールバック実行
        if (this.options.onCancel) {
            this.options.onCancel();
        }
    }
    
    addCheckboxesToItems() {
        // 選択可能なアイテムを取得（data-selectable属性を持つ要素）
        const selectableItems = document.querySelectorAll('[data-selectable="true"]');
        
        selectableItems.forEach(item => {
            // 既にチェックボックスがある場合はスキップ
            if (!item.querySelector('.selection-checkbox')) {
                const checkbox = document.createElement('div');
                checkbox.className = 'selection-checkbox';
                checkbox.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleItemSelection(item);
                });
                item.appendChild(checkbox);
            }

            // カード全体のクリックイベント
            if (!item._selectionClickBound) {
                item.addEventListener('click', (e) => {
                    if (this.isSelectionMode) {
                        e.preventDefault();
                        e.stopPropagation();
                        this.toggleItemSelection(item);
                    } else {
                        // 編集遷移（onEditがあれば呼ぶ）
                        if (this.options.onEdit) {
                            const itemId = this.options.getItemId(item);
                            this.options.onEdit(itemId);
                        }
                    }
                });
                item._selectionClickBound = true;
            }
        });
    }
    
    removeCheckboxesFromItems() {
        const checkboxes = document.querySelectorAll('.selection-checkbox');
        checkboxes.forEach(checkbox => checkbox.remove());
        
        // 選択状態をクリア
        const selectedCards = document.querySelectorAll('.modern-menu-card.selected');
        selectedCards.forEach(card => card.classList.remove('selected'));
    }
    
    toggleItemSelection(item) {
        const itemId = this.options.getItemId(item);
        const checkbox = item.querySelector('.selection-checkbox');
        
        if (this.selectedItems.has(itemId)) {
            this.selectedItems.delete(itemId);
            checkbox.classList.remove('checked');
            item.classList.remove('selected');
        } else {
            this.selectedItems.add(itemId);
            checkbox.classList.add('checked');
            item.classList.add('selected');
        }
        
        this.updateSelectionCount();
        this.updateActionButtons();
    }
    
    updateSelectionCount() {
        const count = this.selectedItems.size;
        this.selectionCount.textContent = `${count}件選択`;
        this.selectionCount.style.display = count > 0 ? 'block' : 'none';
    }
    
    updateActionButtons() {
        const count = this.selectedItems.size;
        
        // 編集ボタンは1つ選択時のみ表示
        this.editFab.style.display = count === 1 ? 'flex' : 'none';
        
        // コピー・削除ボタンは選択がある時のみ有効
        this.copyFab.disabled = count === 0;
        this.deleteFab.disabled = count === 0;
        this.editFab.disabled = count !== 1;
        
        // ボタンの透明度を調整
        this.copyFab.style.opacity = count === 0 ? '0.5' : '1';
        this.deleteFab.style.opacity = count === 0 ? '0.5' : '1';
        this.editFab.style.opacity = count !== 1 ? '0.5' : '1';
    }
    
    async executeCopy() {
        if (this.selectedItems.size === 0) return;
        
        if (this.options.onCopy) {
            await this.options.onCopy(Array.from(this.selectedItems));
        }
    }
    
    async executeDelete() {
        if (this.selectedItems.size === 0) return;
        
        const confirmMessage = `選択した${this.selectedItems.size}件のデータを削除しますか？`;
        if (!confirm(confirmMessage)) return;
        
        if (this.options.onDelete) {
            await this.options.onDelete(Array.from(this.selectedItems));
        }
    }
    
    async executeEdit() {
        if (this.selectedItems.size !== 1) return;
        
        const itemId = Array.from(this.selectedItems)[0];
        if (this.options.onEdit) {
            await this.options.onEdit(itemId);
        }
    }
    
    // 外部から選択状態をリセット
    reset() {
        this.exitSelectionMode();
    }
    
    // 外部から選択状態を取得
    getSelectedItems() {
        return Array.from(this.selectedItems);
    }
    
    // 選択UIの表示/非表示を制御
    show() {
        this.selectFabContainer.style.display = 'flex';
    }
    
    hide() {
        this.selectFabContainer.style.display = 'none';
        this.exitSelectionMode();
    }
}

// グローバル変数として選択UIインスタンスを保持
window.selectionUI = null; 