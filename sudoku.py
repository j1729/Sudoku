import sys
import numpy as np
from PyQt5.QtCore import Qt, QAbstractTableModel, QVariant
from PyQt5.QtWidgets import QTableView, QMainWindow, QApplication, QPushButton, QMessageBox
from PyQt5.QtGui import QColor, QFont, QPainter, QPen

# Algorithm X via Dancing Links:
# https://arxiv.org/pdf/cs/0011047.pdf

class Node:
    ''' Node in a 2D linked list.  There will be four different kinds of nodes:
        root node: serves no other purpose than a place-holder in the top-left corner
        column node: first row of nodes, contains a size field that tells you how many value nodes are in it
        row node: first column of nodes on left, contains name field which we need to identify solution
        value node: this corresponds to a 1 in the index matrix for the row and column it is associated with '''
    def __init__(self, name=None):
        self.up = self.down = self.right = self.left = self.column = self.row = self
        if name:
            self.name = name

class DLX:
    ''' Dancing Links '''
    def __init__(self, idx_matrix, idx_names):
        self.rows, self.cols = idx_matrix.shape
        self.root = Node()

        # add column nodes:
        for j in range(self.cols):
            col_node = Node()
            col_node.left = self.root.left
            col_node.right = self.root
            col_node.size = 0
            self.root.left.right = col_node
            self.root.left = col_node

        # populate matrix rows:
        for i in range(self.rows):
            col_node = self.root
            row_node = Node(idx_names[i])
            row_node.down = self.root
            row_node.up = self.root.up
            row_node.column = col_node
            self.root.up.down = row_node
            self.root.up = row_node
            for j in range(self.cols):
                col_node = col_node.right
                if idx_matrix[i, j]:
                    value_node = Node()
                    value_node.left = row_node.left
                    value_node.right = row_node
                    value_node.up = col_node.up
                    value_node.down = value_node.column = col_node
                    value_node.row = row_node
                    row_node.left.right = value_node
                    row_node.left = value_node
                    col_node.size += 1
                    col_node.up.down = value_node
                    col_node.up = value_node

    def cover_col(self, col_node):
        ''' cover whole column in matrix '''
        value_node = col_node
        while True:
            value_node.left.right = value_node.right
            value_node.right.left = value_node.left
            value_node = value_node.down
            if value_node == col_node:
                break
        self.cols -= 1

    def uncover_col(self, col_node):
        ''' uncover whole column in matrix '''
        value_node = col_node
        while True:
            value_node = value_node.up
            value_node.left.right = value_node
            value_node.right.left = value_node
            if value_node == col_node:
                break
        self.cols += 1

    def cover_row(self, row_node):
        ''' cover whole row in matrix '''
        value_node = row_node
        while True:
            value_node.up.down = value_node.down
            value_node.down.up = value_node.up
            value_node = value_node.right
            if value_node == row_node:
                break
        self.rows -= 1

    def uncover_row(self, row_node):
        ''' uncover whole row in matrix '''
        value_node = row_node
        while True:
            value_node = value_node.left
            value_node.up.down = value_node
            value_node.down.up = value_node
            if value_node == row_node:
                break
        self.rows += 1

    def cover_col_rows(self, col_node):
        ''' cover column and all rows that are in it '''
        self.cover_col(col_node)
        value_node = col_node.down
        while value_node != col_node:
            self.cover_row(value_node.row)
            value_node = value_node.down

    def uncover_col_rows(self, col_node):
        ''' uncover column and all rows that are in it '''
        value_node = col_node.up
        while value_node != col_node:
            self.uncover_row(value_node.row)
            value_node = value_node.up
        self.uncover_col(col_node)

    def cover_row_cols_rows(self, row_node):
        ''' cover row and all columns that are in it, plus all rows that are in each of these columns '''
        self.cover_row(row_node)
        value_node = row_node.right
        while value_node != row_node:
            self.cover_col_rows(value_node.column)
            value_node = value_node.right

    def uncover_row_cols_rows(self, row_node):
        ''' uncover row and all columns that are in it, plus all rows that are in each of these columns '''
        value_node = row_node.left
        while value_node != row_node:
            self.uncover_col_rows(value_node.column)
            value_node = value_node.left
        self.uncover_row(row_node)

    def get_matrix(self):
        ''' prints the index matrix (useful for debugging) '''
        idx_matrix = np.zeros((self.rows, self.cols), dtype=int)
        column_node = self.root
        row_node = self.root
        for i in range(self.rows):
            row_node = row_node.down
            value_node = row_node.right
            for j in range(self.cols):
                column_node = column_node.right
                if value_node.column == column_node:
                    idx_matrix[i, j] = 1
                    value_node = value_node.right
            column_node = column_node.right
        return idx_matrix

    def solve(self):
        ''' returns list of row names if solution exists, otherwise None '''
        # if no more data, solution has been found:
        if self.root.right == self.root:
            return []

        # pick column that minimizes branching factor:
        column_node = self.root.right
        c_min = column_node
        while column_node != self.root:
            if column_node.size < c_min.size:
                c_min = column_node
            column_node = column_node.right

        # if there are no more options, no solution:
        if c_min.size == 0:
            return None

        # dancing links:
        self.cover_col_rows(c_min)
        value_node = c_min.down
        sol = None
        while value_node != c_min:
            self.cover_row_cols_rows(value_node.row)
            sol = self.solve()
            self.uncover_row_cols_rows(value_node.row)
            if sol is not None:
                break
            value_node = value_node.down
        self.uncover_col_rows(c_min)

        # return solutions:
        if sol is not None:
            return [value_node.row.name] + sol

        return None


# Sudoku GUI:

CELL_SIZE = 30
FONT_SIZE = 12

class InconsistentInputs(Exception):
    ''' raised when there is no solution '''


class TableModel(QAbstractTableModel):
    ''' Custom model for storing display data.  We use two Numpy arrays, one for user data (displayed in black) that
        the user enters, and another for solver data (displayed in blue) that we will compute and enter. '''
    def __init__(self, user_data, solver_data):
        super().__init__()
        self._user_data = user_data             # data that user types in
        self._solver_data = solver_data         # data that gets solved

        # sudoku encoding into index matrix:
        # all rows are named (val, (row, col)) which means that the number val appears at (row, col) in the grid
        # so there are 9^3 = 729 rows
        # the columns are the constraints:
        # 0 through 80: only one value per location in the grid, so this is just the location in the grid,
        # traversing left-to-right, then top-to-bottom
        # 81 through 161: only one value per column, so this is just value 1 through 9 x columns 1 through 9
        # 162 through 242: only one value per row, so this is just value 1 through 9 x rows 1 through 9
        # 243 through 323: only one value per group, so this is just value 1 through 9 x groups 1 through 9
        # total constraint columns = 81 * 4 = 324
        sudoku_matrix = np.zeros((9 ** 3, 9 ** 2 * 4))
        sudoku_names = []
        for i in range(9):
            for j in range(81):
                row = j // 9
                col = j % 9
                sudoku_names.append((i + 1, (row, col)))
                group = 3 * (row // 3) + (col // 3)
                row_idx = i * 81 + j
                sudoku_matrix[row_idx, j] = 1
                sudoku_matrix[row_idx, 81 + i * 9 + row] = 1
                sudoku_matrix[row_idx, 2 * 81 + i * 9 + col] = 1
                sudoku_matrix[row_idx, 3 * 81 + i * 9 + group] = 1
        self._dlx = DLX(sudoku_matrix, sudoku_names)

    def setData(self, index, value):
        ''' sets data point that the user enters '''
        row = index.row()
        col = index.column()

        # if we set something different, remove all solved data, since it's now wrong
        if self._solver_data[row, col] != 0 and self._solver_data[row, col] != value:
            self._solver_data[:] = 0

        self._user_data[row, col] = value

    def clearData(self):
        ''' user clears all data '''
        self._user_data[:] = 0
        self._solver_data[:] = 0

    def solve(self):
        ''' Solve the Sudoku by first covering all rows corresponding to what the user has selected, and then finding
            if rest of solution exists.  If not, raise a warning.  Either way, we uncover everything when we're done
            so that we can reuse the same linked list. '''
        self._solver_data = self._user_data.copy()
        covers = []

        try:
            for i in range(9):
                for j in range(9):
                    val = self._user_data[i, j]
                    if val:
                        node_name = (val, (i, j))
                        node = self._dlx.root.down
                        found = False
                        while node != self._dlx.root:
                            if node.name == node_name:
                                found = True
                                self._dlx.cover_row_cols_rows(node)
                                covers.append(node)
                                break
                            node = node.down
                        if not found:
                            raise InconsistentInputs('Inconsistent!')
            sol = self._dlx.solve()
            if sol is None:
                raise InconsistentInputs('Inconsistent!')
            for val, (i, j) in sol:
                self._solver_data[i, j] = val
        except InconsistentInputs as e:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText(str(e))
            msg.setInformativeText("No solution exists, please check your inputs.")
            msg.setWindowTitle("No Solution:")
            msg.exec_()
        finally:
            while covers:
                node = covers.pop()
                self._dlx.uncover_row_cols_rows(node)


    def data(self, index, role):
        ''' returns the data stored under the given role for the item referred to by the index '''
        if role == Qt.DisplayRole:
            return str(self._user_data[index.row(), index.column()] or
                       self._solver_data[index.row(), index.column()] or '')
        if role == Qt.BackgroundRole:
            if (index.row() // 3 + index.column() // 3) % 2 == 1:
                return QColor('lightgrey')
        elif role == Qt.ForegroundRole:
            if self._user_data[index.row(), index.column()] == 0 \
                and self._solver_data[index.row(), index.column()] > 0:
                return QColor('blue')
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter + Qt.AlignHCenter
        elif role == Qt.FontRole:
            return QFont('Times', FONT_SIZE)
        return QVariant()

    def rowCount(self, *_):
        ''' returns number of rows '''
        return self._solver_data.shape[0]

    def columnCount(self, *_):
        ''' returns number of columns '''
        return self._solver_data.shape[1]


class MyTableView(QTableView):
    ''' Custom table view allows us to catch key events and draws thicker lines separating groups. '''
    def paintEvent(self, event):
        ''' paints thicker lines separating groups '''
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        pen = QPen(Qt.black, 3)
        painter.setPen(pen)
        painter.drawLine(3 * CELL_SIZE - 1, 0, 3 * CELL_SIZE - 1, 9 * CELL_SIZE - 2)
        painter.drawLine(6 * CELL_SIZE - 1, 0, 6 * CELL_SIZE - 1, 9 * CELL_SIZE - 2)
        painter.drawLine(0, 3 * CELL_SIZE - 1, 9 * CELL_SIZE - 2, 3 * CELL_SIZE - 1)
        painter.drawLine(0, 6 * CELL_SIZE - 1, 9 * CELL_SIZE - 2, 6 * CELL_SIZE - 1)

    def keyPressEvent(self, event):
        ''' catches key press activity for user to edit data '''
        key = event.key()
        if (Qt.Key_1 <= key <= Qt.Key_9) or key == Qt.Key_Delete:
            idx = self.selectionModel().currentIndex()
            val = key - Qt.Key_0 if key != Qt.Key_Delete else 0
            self.model().setData(idx, val)
            self.viewport().update()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    ''' Main window contains Sudoku grid and two click buttons '''
    def __init__(self):
        super().__init__()

        self.table = MyTableView()

        user_data = np.zeros((9, 9), dtype=int)
        solver_data = np.zeros((9, 9), dtype=int)
        self.model = TableModel(user_data, solver_data)
        self.table.setModel(self.model)

        for i in range(9):
            self.table.setColumnWidth(i, CELL_SIZE)
            self.table.setRowHeight(i, CELL_SIZE)

        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.setCentralWidget(self.table)

        button_clear = QPushButton(self)
        button_width = button_clear.frameGeometry().width()
        button_height = button_clear.frameGeometry().height()
        button_clear.setText("Clear")
        button_clear.move(CELL_SIZE * 9 // 2 - button_width - 5, 9 * CELL_SIZE + 10)
        button_clear.clicked.connect(self.button_clear)

        button_solve = QPushButton(self)
        button_solve.setText("Solve")
        button_solve.move(CELL_SIZE * 9 // 2 + 5, 9 * CELL_SIZE + 10)
        button_solve.clicked.connect(self.button_solve)

        self.setFixedSize(9 * CELL_SIZE + 2, 9 * CELL_SIZE + button_height + 20)
        self.setWindowTitle('Sudoku Solver')

    def button_clear(self):
        ''' clear all data '''
        self.model.clearData()
        self.table.viewport().update()

    def button_solve(self):
        ''' solve rest of puzzle '''
        self.model.solve()
        self.table.viewport().update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()
