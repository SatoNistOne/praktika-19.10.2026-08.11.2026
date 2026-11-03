import json
import logging
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import mysql.connector

from database import Warehouse, export_csv

BASE = Path(__file__).resolve().parent
TITLES = {'products': 'Товары', 'stock_movements': 'Движения',
          'suppliers': 'Поставщики', 'categories': 'Категории', 'report': 'Отчет о движении'}
COLUMNS = {
 'products': [('sku','Артикул'),('name','Название'),('category','Категория'),('unit','Ед.'),('min_stock','Минимум'),('balance','Остаток')],
 'suppliers': [('name','Поставщик'),('phone','Телефон')],
 'categories': [('name','Категория')],
 'stock_movements': [('movement_date','Дата'),('product','Товар'),('kind','Тип'),('quantity','Количество'),('supplier','Поставщик'),('note','Примечание')],
 'report': [('sku','Артикул'),('name','Товар'),('unit','Ед.'),('opening','Начало'),('incoming','Приход'),('outgoing','Расход'),('closing','Конец')]
}


class App(tk.Tk):
    def __init__(self, warehouse):
        super().__init__()
        self.db = warehouse
        self.title('Складской учет товаров — УП.02')
        self.geometry('1200x760')
        self.minsize(1050, 650)
        self.configure(bg='#f4f6fa')
        self.page = 'products'
        self.rows = []
        self.widgets = {}
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('DejaVu Sans', 11))
        style.configure('TFrame', background='#f4f6fa')
        style.configure('TLabel', background='#f4f6fa', foreground='#1e3048')
        style.configure('TButton', padding=(12,8))
        style.configure('Accent.TButton', background='#2865bf', foreground='white')
        style.configure('Treeview', rowheight=38, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('DejaVu Sans',10,'bold'), padding=8)
        style.map('Treeview', background=[('selected','#d7e6fc')], foreground=[('selected','#172c49')])
        side = tk.Frame(self, bg='#172c49', width=190)
        side.pack(side='left', fill='y'); side.pack_propagate(False)
        tk.Label(side, text='СКЛАД / 03', bg='#172c49', fg='white', font=('DejaVu Sans',18,'bold')).pack(pady=(28,8))
        tk.Label(side,text='Учебный проект',bg='#172c49',fg='#b4c6df').pack(pady=(0,35))
        for key, title in TITLES.items():
            tk.Button(side, text=title, anchor='w', padx=18, pady=14,
                bg='#172c49', fg='white', activebackground='#28496f', activeforeground='white',
                relief='flat', borderwidth=0, command=lambda k=key:self.safe(lambda:self.show(k))).pack(fill='x')
        tk.Label(side,text='Python + MySQL',bg='#172c49',fg='#b4c6df').pack(side='bottom',pady=25)
        self.body = ttk.Frame(self, padding=25); self.body.pack(fill='both',expand=True)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.safe(lambda:self.show('products'))

    def safe(self, action):
        try:
            return action()
        except ValueError as exc:
            messagebox.showwarning('Проверьте данные',str(exc),parent=self)
        except mysql.connector.Error as exc:
            logging.exception('Database operation failed')
            if exc.errno == 1062:
                message = 'Запись с таким названием или артикулом уже существует.'
            elif exc.errno in (1451,1452):
                message = 'Связанная запись используется или отсутствует. Проверьте справочники.'
            else:
                message = 'Операция с базой не выполнена. Проверьте подключение и журнал приложения.'
            messagebox.showerror('Ошибка базы данных',message,parent=self)
        except OSError:
            logging.exception('File operation failed')
            messagebox.showerror('Ошибка файла','Не удалось записать файл. Проверьте путь и права.',parent=self)

    def show(self, page):
        self.page = page
        self.widgets = {}
        for widget in self.body.winfo_children(): widget.destroy()
        top = ttk.Frame(self.body); top.pack(fill='x',pady=(0,24))
        ttk.Label(top,text=TITLES[page],font=('DejaVu Sans',24,'bold')).pack(side='left')
        if page != 'report':
            ttk.Button(top,text='+ Добавить',style='Accent.TButton',command=lambda:self.safe(self.edit)).pack(side='right')
        filters = ttk.Frame(self.body); filters.pack(fill='x',pady=(0,15))
        if page == 'products':
            self.search = tk.StringVar()
            ttk.Entry(filters,textvariable=self.search,width=27).pack(side='left',padx=(0,8))
            self.categories = {'Все категории': None}
            for row in self.db.reference('categories'):
                self.categories[f"{row['name']} [#{row['id']}]"] = row['id']
            self.category = ttk.Combobox(filters,values=list(self.categories),state='readonly',width=23)
            self.category.current(0); self.category.pack(side='left',padx=5)
            self.low = tk.BooleanVar()
            ttk.Checkbutton(filters,text='Ниже минимума',variable=self.low).pack(side='left',padx=8)
            ttk.Button(filters,text='Найти',command=lambda:self.safe(self.refresh)).pack(side='left')
            self.search.trace_add('write',lambda *args:None)
            self.bind('<Return>',lambda event:self.safe(self.refresh))
        elif page in ('stock_movements','report'):
            ttk.Label(filters,text='Период с').pack(side='left')
            self.start = ttk.Entry(filters,width=12); self.start.insert(0,'2026-10-19'); self.start.pack(side='left',padx=8)
            ttk.Label(filters,text='по').pack(side='left')
            self.end = ttk.Entry(filters,width=12); self.end.insert(0,'2026-11-08'); self.end.pack(side='left',padx=8)
            ttk.Button(filters,text='Сформировать' if page=='report' else 'Показать',command=lambda:self.safe(self.refresh)).pack(side='left')
        columns = COLUMNS[page]
        frame = ttk.Frame(self.body); frame.pack(fill='both',expand=True)
        self.tree = ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',selectmode='browse')
        for key,label in columns:
            self.tree.heading(key,text=label)
            widths = {'name':210,'product':210,'supplier':220,'category':220,
                      'note':230,'unit':65,'sku':90,'min_stock':95,'balance':95}
            width = widths.get(key,110)
            self.tree.column(key,width=width,minwidth=width,anchor='w',stretch=True)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview)
        xscroll = ttk.Scrollbar(frame,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set,xscrollcommand=xscroll.set)
        self.tree.grid(row=0,column=0,sticky='nsew'); scroll.grid(row=0,column=1,sticky='ns'); xscroll.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        self.tree.tag_configure('low',foreground='#ad471e',background='#fff3eb')
        foot = ttk.Frame(self.body); foot.pack(fill='x',pady=(18,0))
        if page != 'report':
            ttk.Button(foot,text='Изменить',command=lambda:self.safe(lambda:self.edit(self.selected()))).pack(side='left',padx=(0,8))
            ttk.Button(foot,text='Удалить',command=lambda:self.safe(self.delete)).pack(side='left')
        ttk.Button(foot,text='Экспорт CSV',command=lambda:self.safe(self.export)).pack(side='right')
        self.status = ttk.Label(self.body,text=''); self.status.pack(anchor='w',pady=(16,0))
        self.safe(self.refresh)

    def refresh(self):
        if self.page == 'products':
            rows = self.db.products(self.search.get(),self.categories[self.category.get()],self.low.get())
        elif self.page == 'report': rows = self.db.report(self.start.get(),self.end.get())
        elif self.page == 'stock_movements': rows = self.db.movements(self.start.get(),self.end.get())
        else: rows = self.db.reference(self.page)
        self.rows = rows
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(rows):
            values = [row[key] for key,label in COLUMNS[self.page]]
            if self.page=='stock_movements': values[2] = 'Поступление' if row['kind']=='IN' else 'Списание'
            tags = ('low',) if self.page=='products' and row['balance']<row['min_stock'] else ()
            self.tree.insert('', 'end', iid=str(i),values=values,tags=tags)
        suffix = '  •  Оранжевым отмечен остаток ниже минимума' if self.page=='products' else ''
        self.status.configure(text=f'Записей: {len(rows)}{suffix}')

    def selected(self):
        selection = self.tree.selection()
        if not selection: raise ValueError('Сначала выберите строку.')
        return self.rows[int(selection[0])]

    def edit(self, row=None):
        page = self.page
        dialog = tk.Toplevel(self); dialog.title('Изменение записи' if row else 'Новая запись')
        dialog.geometry('540x570'); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog,padding=25); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=TITLES[page],font=('DejaVu Sans',18,'bold')).pack(anchor='w',pady=(0,15))
        controls = {}; maps = {}
        def field(key,label,default='',options=None,disabled=False):
            ttk.Label(frame,text=label).pack(anchor='w',pady=(6,3))
            if options is not None:
                maps[key] = options
                widget = ttk.Combobox(frame,values=list(options),state='readonly')
                match = next((name for name,value in options.items() if value==default),None)
                widget.set(match or next(iter(options),''))
            else:
                widget = ttk.Entry(frame); widget.insert(0,str(default))
            widget.pack(fill='x')
            if disabled: widget.configure(state='disabled')
            controls[key] = widget
        data = row or {}
        if page in ('categories','suppliers','products'):
            if page=='products': field('sku','Артикул',data.get('sku',''))
            field('name','Название',data.get('name',''))
            if page=='suppliers': field('phone','Телефон (необязательно)',data.get('phone',''))
            if page=='products':
                options = {f"{r['name']} [#{r['id']}]":r['id'] for r in self.db.reference('categories')}
                field('category_id','Категория',data.get('category_id'),options)
                field('unit','Единица измерения',data.get('unit','шт.'))
                field('min_stock','Минимальный остаток',data.get('min_stock',0))
        else:
            options = {f"{r['name']} [#{r['id']}]":r['id'] for r in self.db.reference('products')}
            field('product_id','Товар',data.get('product_id'),options,disabled=bool(row))
            field('movement_date','Дата (ГГГГ-ММ-ДД)',data.get('movement_date',date.today().isoformat()))
            field('kind','Тип',data.get('kind','IN'),{'Поступление':'IN','Списание':'OUT'})
            suppliers = {'Не выбран':None}
            suppliers.update({f"{r['name']} [#{r['id']}]":r['id'] for r in self.db.reference('suppliers')})
            field('supplier_id','Поставщик (только для поступления)',data.get('supplier_id'),suppliers)
            field('quantity','Количество (целое)',data.get('quantity',1))
            field('note','Примечание',data.get('note',''))
        def save():
            values = {key:maps[key].get(w.get()) if key in maps else w.get() for key,w in controls.items()}
            if page=='stock_movements': self.db.save_movement(values,data.get('id'))
            else: self.db.save_reference(page,values,data.get('id'))
            dialog.destroy(); self.refresh()
        buttons = ttk.Frame(frame); buttons.pack(fill='x',pady=20)
        ttk.Button(buttons,text='Сохранить',style='Accent.TButton',command=lambda:self.safe(save)).pack(side='left')
        ttk.Button(buttons,text='Отмена',command=dialog.destroy).pack(side='right')
        self.active_dialog = dialog
        self.widgets = controls

    def delete(self):
        row = self.selected()
        if not messagebox.askyesno('Удаление','Удалить выбранную запись?',parent=self): return
        if self.page=='stock_movements': self.db.delete_movement(row['id'])
        else: self.db.delete_reference(self.page,row['id'])
        self.refresh()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if path:
            export_csv(path,self.rows,COLUMNS[self.page])
            self.status.configure(text='CSV сохранен: '+path)

    def close(self):
        self.db.connection.close(); self.destroy()


def connect(config_path):
    with open(config_path,encoding='utf-8') as file: config = json.load(file)
    return mysql.connector.connect(**config,autocommit=True,connection_timeout=5)


def main():
    logging.basicConfig(filename=BASE/'app.log',level=logging.WARNING,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        connection = connect(BASE/'config.json')
    except (OSError,ValueError,mysql.connector.Error):
        logging.exception('Connection failed')
        root=tk.Tk(); root.withdraw()
        messagebox.showerror('Подключение','Не удалось подключиться. Создайте config.json по образцу и проверьте MySQL.')
        root.destroy(); return
    App(Warehouse(connection)).mainloop()


if __name__ == '__main__': main()
