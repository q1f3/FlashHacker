from PySide.QtCore import *
from PySide.QtGui import *
from PySide.QtSql import *
import os
import subprocess
import shutil

from FlashManipulation import *

class ConfigurationDialog(QDialog):
	def __init__(self,parent=None,rabcdasm='',log_level=0):
		super(ConfigurationDialog,self).__init__(parent)
		self.setWindowTitle("Configuration")
		self.setWindowIcon(QIcon('DarunGrim.png'))

		rabcdasm_button=QPushButton('RABCDAsm Path:',self)
		rabcdasm_button.clicked.connect(self.getRABCDasmPath)
		self.rabcdasm_line=QLineEdit("")
		self.rabcdasm_line.setAlignment(Qt.AlignLeft)
		self.rabcdasm_line.setMinimumWidth(250)
		self.rabcdasm_line.setText(rabcdasm)

		buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
		buttonBox.accepted.connect(self.accept)
		buttonBox.rejected.connect(self.reject)

		main_layout=QGridLayout()
		main_layout.addWidget(rabcdasm_button,0,0)
		main_layout.addWidget(self.rabcdasm_line,0,1)

		main_layout.addWidget(buttonBox,6,1)

		self.setLayout(main_layout)

	def keyPressEvent(self,e):
		key=e.key()

		if key==Qt.Key_Return or key==Qt.Key_Enter:
			return
		else:
			super(ConfigurationDialog,self).keyPressEvent(e)

	def getRABCDasmPath(self):
		dir_name=QFileDialog.getExistingDirectory(self,'FileStore Dir')
		if dir_name:
			self.rabcdasm_line.setText(dir_name)

class TreeItem(object):
	def __init__(self,data,parent=None,assoc_data=None):
		self.parentItem=parent
		self.itemData=data
		self.assocData=assoc_data
		self.childItems=[]

	def appendChild(self,item):
		self.childItems.append(item)

	def child(self,row):
		return self.childItems[row]

	def childCount(self):
		return len(self.childItems)

	def columnCount(self):
		return len(self.itemData)

	def getAssocData(self):
		return self.assocData

	def data(self,column):
		try:
			return self.itemData[column]
		except:
			pass

	def parent(self):
		return self.parentItem

	def row(self):
		if self.parentItem:
			return self.parentItem.childItems.index(self)
		return 0

class TreeModel(QAbstractItemModel):
	def __init__(self,root_item,parent=None):
		super(TreeModel, self).__init__(parent)
		self.DirItems={}
		self.rootItem=TreeItem(root_item)
		self.setupModelData()

	def addDir(self,dir):
		dir_item=TreeItem((os.path.basename(dir),))
		self.rootItem.appendChild(dir_item)
		self.DirItems[dir]=dir_item

		asasm=ASASM()
		for relative_file in asasm.EnumDir(dir):
			item=TreeItem((relative_file,),dir_item)
			dir_item.appendChild(item)

	def showClasses(self,assemblies):
		for root_dir in assemblies.keys():
			class_names=assemblies[root_dir].keys()
			class_names.sort()

			for class_name in class_names:
				dir_item=TreeItem((class_name,))
				self.rootItem.appendChild(dir_item)

				[parsed_lines,methods]=assemblies[root_dir][class_name]
				for [refid,[blocks,maps,labels,parents,body_parameters]] in methods.items():
					item=TreeItem((refid,),dir_item,(root_dir, class_name, refid))
					dir_item.appendChild(item)

	def showAPIs(self,api_names):
		api_names_list=api_names.keys()
		api_names_list.sort()
		for api_name in api_names_list:
			dir_item=TreeItem((api_name,"API"))
			self.rootItem.appendChild(dir_item)
			for [op,root_dir,class_name,refid,block_id,block_line_no] in api_names[api_name]:
				item=TreeItem((refid,op,),dir_item,(op,root_dir,class_name,refid,block_id,block_line_no))
				dir_item.appendChild(item)

	def setupModelData(self):
		pass

	def columnCount(self,parent):
		if parent.isValid():
			return parent.internalPointer().columnCount()
		else:
			return self.rootItem.columnCount()

	def getAssocData(self,index):
		if not index.isValid():
			return None

		item=index.internalPointer()
		return item.getAssocData()

	def data(self,index,role):
		if not index.isValid():
			return None

		if role!=Qt.DisplayRole:
			return None

		item=index.internalPointer()
		return item.data(index.column())

	def headerData(self,section,orientation,role):
		if orientation==Qt.Horizontal and role==Qt.DisplayRole:
			return self.rootItem.data(section)

		return None

	def index(self,row,column,parent):
		if not self.hasIndex(row,column,parent):
			return QModelIndex()

		if not parent.isValid():
			parentItem = self.rootItem
		else:
			parentItem=parent.internalPointer()

		childItem=parentItem.child(row)

		if childItem:
			return self.createIndex(row,column,childItem)
		else:
			return QModelIndex()

	def parent(self,index):
		if not index.isValid():
			return QModelIndex()

		childItem=index.internalPointer()
		parentItem=childItem.parent()

		if parentItem!=None:
			if parentItem==self.rootItem:
				return QModelIndex()

			return self.createIndex(parentItem.row(),0,parentItem)
		return QModelIndex()

	def rowCount(self,parent):
		if parent.column()>0:
			return 0

		if not parent.isValid():
			parentItem=self.rootItem
		else:
			parentItem=parent.internalPointer()

		return parentItem.childCount()

	def flags(self,index):
		if not index.isValid():
			return Qt.NoItemFlags

		return Qt.ItemIsEnabled|Qt.ItemIsSelectable

class MainWindow(QMainWindow):
	UseDock=False
	ShowBBMatchTableView=False

	def __init__(self):
		super(MainWindow,self).__init__()
		self.setWindowTitle("Flash Hacker")
		self.readSettings()

		self.Directories=[]
		self.SWFFilename=''

		vertical_splitter=QSplitter()
		
		tab_widget=QTabWidget()
		self.classTreeView=QTreeView()
		tab_widget.addTab(self.classTreeView,"Classes")
		self.apiTreeView=QTreeView()
		tab_widget.addTab(self.apiTreeView,"API")

		vertical_splitter.addWidget(tab_widget)

		self.graph=MyGraphicsView()
		self.graph.setRenderHints(QPainter.Antialiasing)
		vertical_splitter.addWidget(self.graph)
		vertical_splitter.setStretchFactor(0,0)
		vertical_splitter.setStretchFactor(1,1)

		main_widget=QWidget()
		vlayout=QVBoxLayout()
		vlayout.addWidget(vertical_splitter)
		main_widget.setLayout(vlayout)
		self.setCentralWidget(main_widget)
		
		self.createMenus()

		self.restoreUI()
		self.show()

	DebugFileOperation=0
	def open(self):
		abcexport=os.path.join(self.RABCDAsmPath,"abcexport.exe")
		rabcdasm=os.path.join(self.RABCDAsmPath,"rabcdasm.exe")
		filename = QFileDialog.getOpenFileName(self,"Open SWF","","SWF Files (*.swf)")[0]

		if filename:
			self.SWFFilename=filename

			if self.DebugFileOperation>0:
				print subprocess.Popen("%s %s" % (abcexport,filename), shell=True, stdout=subprocess.PIPE).stdout.read()

			dir_name=os.path.dirname(filename)
			base_filename='.'.join(os.path.basename(filename).split('.')[0:-1])

			i=0
			abc_dirnames=[]
			while True:
				abc_filename=os.path.join(dir_name,'%s-%d.abc' % (base_filename,i))
				abc_filename=abc_filename.replace('/','\\')

				if os.path.isfile(abc_filename):
					if self.DebugFileOperation>0:
						print 'abc_filename:', abc_filename
					output=subprocess.Popen("%s %s" % (rabcdasm,abc_filename), shell=True, stdout=subprocess.PIPE).stdout.read()

					if self.DebugFileOperation>0:
						print output

					abc_dirname=os.path.join(dir_name,'%s-%d' % (base_filename,i))

					if self.DebugFileOperation>0:
						print 'abc_dirname:', abc_dirname
					if os.path.isdir(abc_dirname):
						if self.DebugFileOperation>0:
							print 'Disasm succeeded', abc_dirname
						abc_dirnames.append(abc_dirname)
				else:
					break
				i+=1

			self.showDir(abc_dirnames)

	def save(self):
		rabcasm=os.path.join(self.RABCDAsmPath,"rabcasm.exe")
		abcreplace=os.path.join(self.RABCDAsmPath,"abcreplace.exe")

		if self.DebugFileOperation>0:	
			print 'self.SWFFilename:',self.SWFFilename

		if self.SWFFilename:
			dir_name=os.path.dirname(self.SWFFilename)
			base_name=os.path.basename(self.SWFFilename)
			main_name='.'.join(base_name.split('.')[0:-1])
			i=0
			target_root_dir=dir_name 

			while True:
				main_asasm_file=os.path.join(target_root_dir,'%s-%d\%s-%d.main.asasm' % (main_name,i,main_name,i)).replace('/','\\')
				abc_file=os.path.join(target_root_dir,'%s-%d\%s-%d.main.abc' % (main_name,i,main_name,i)).replace('/','\\')

				if self.DebugFileOperation>0:
					print 'main_asasm_file:',main_asasm_file
				if not os.path.isfile(main_asasm_file):
					break

				if self.DebugFileOperation>0:
					print 'Assembling', main_asasm_file

				cmdline="%s %s" % (rabcasm,main_asasm_file)

				if self.DebugFileOperation>-1:
					print '* Executing: %s' % cmdline

				output=subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE).stdout.read()
				if self.DebugFileOperation>-1:
					print output

				swf_outputfilename=os.path.join(target_root_dir,'%s-mod.swf' % main_name).replace('/','\\')

				if self.DebugFileOperation>0:
					print 'swf_outputfilename:', swf_outputfilename
				try:
					shutil.copy(self.SWFFilename,swf_outputfilename)
				except:
					import traceback
					traceback.print_exc()

				cmdline="%s %s %d %s" % (abcreplace,swf_outputfilename,i,abc_file)

				if self.DebugFileOperation>-1:
					print '* Executing: %s' % cmdline

				output=subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE).stdout.read()
				if self.DebugFileOperation>-1:
					print output

				i+=1

		"""
		TODO:
		mkdir Util-0
		copy Scripts\Util-0\* Util-0\
		"""

	def openDirectory(self):
		dialog=QFileDialog()
		dialog.setFileMode(QFileDialog.Directory)
		dialog.setOption(QFileDialog.ShowDirsOnly)
		directory=dialog.getExistingDirectory(self,"Choose Directory",os.getcwd())
		if directory:
			self.showDir([directory])

	def addMethodTrace(self):
		target_root_dir=os.path.dirname(self.SWFFilename)
		self.asasm.Instrument(target_root_dir=target_root_dir,operations=[["AddMethodTrace",'']])

	def addBasicBlockTrace(self):
		target_root_dir=os.path.dirname(self.SWFFilename)
		self.asasm.Instrument(target_root_dir=target_root_dir,operations=[["AddBasicBlockTrace",'']])

	def addAPITrace(self):
		target_root_dir=os.path.dirname(self.SWFFilename)
		self.asasm.Instrument(target_root_dir=target_root_dir,operations=[["AddAPITrace",''], ["Include",["../Util-0/Util.script.asasm"]]])

	def createMenus(self):
		self.fileMenu=self.menuBar().addMenu("&File")
		self.openAct=QAction("&Open SWF file...",
									self,
									triggered=self.open)
		self.fileMenu.addAction(self.openAct)

		self.saveAct=QAction("&Save...",
									self,
									triggered=self.save)
		self.fileMenu.addAction(self.saveAct)

		self.openDirAct=QAction("&Open directory...",
									self,
									shortcut=QKeySequence.Open,
									statusTip="Open an existing folder", 
									triggered=self.openDirectory)
		self.fileMenu.addAction(self.openDirAct)

		self.instrumentMenu=self.menuBar().addMenu("&Instrument")

		self.addMethodTraceAct=QAction("&Add method traces...",
									self,
									triggered=self.addMethodTrace)
		self.instrumentMenu.addAction(self.addMethodTraceAct)

		self.addBasicBlockTraceAct=QAction("&Add basic block traces...",
									self,
									triggered=self.addBasicBlockTrace)
		self.instrumentMenu.addAction(self.addBasicBlockTraceAct)

		self.addAPITraceAct=QAction("&Add API traces...",
									self,
									triggered=self.addAPITrace)
		self.instrumentMenu.addAction(self.addAPITraceAct)

	def showDir(self,dirs):
		self.Directories=dirs
		self.asasm=ASASM()	
		self.Assemblies=self.asasm.RetrieveAssemblies(dirs)

		self.treeModel=TreeModel(("Name",))
		self.treeModel.showClasses(self.Assemblies)
		self.classTreeView.setModel(self.treeModel)
		self.classTreeView.connect(self.classTreeView.selectionModel(),SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), self.classTreeSelected)
		self.classTreeView.expandAll()
		#self.classTreeView.setSelectionMode(QAbstractItemView.MultiSelection)

		[local_names,api_names]=self.asasm.GetNames()
		self.apiTreeModel=TreeModel(("Name",""))
		self.apiTreeModel.showAPIs(api_names)
		self.apiTreeView.setModel(self.apiTreeModel)
		self.apiTreeView.connect(self.apiTreeView.selectionModel(),SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), self.apiTreeSelected)
		self.apiTreeView.expandAll()

	def classTreeSelected(self, newSelection, oldSelection):
		for index in newSelection.indexes():
			item_data=self.treeModel.getAssocData(index)
			if item_data!=None:
				(root_dir,class_name,refid)=item_data
				[parsed_lines,methods]=self.Assemblies[root_dir][class_name]
				#[blocks,maps,labels,parents,body_parameters]=methods[refid]

				[disasms,links,address2name]=self.asasm.ConvertMapsToPrintable(methods[refid])
				self.graph.DrawFunctionGraph("Target", disasms, links, address2name=address2name)

	def apiTreeSelected(self, newSelection, oldSelection):
		for index in newSelection.indexes():
				item_data=self.treeModel.getAssocData(index)
				if item_data!=None:
					(op,root_dir,class_name,refid,block_id,block_line_no)=item_data
					
					[parsed_lines,methods]=self.Assemblies[root_dir][class_name]
					[disasms,links,address2name]=self.asasm.ConvertMapsToPrintable(methods[refid])
					self.graph.DrawFunctionGraph("Target", disasms, links, address2name=address2name)
					self.graph.HilightAddress(block_id)

	def showConfiguration(self):
		dialog=ConfigurationDialog(rabcdasm=self.RABCDAsmPath)
		if dialog.exec_():
			self.RABCDAsmPath=dialog.rabcdasm_line.text()

	def readSettings(self):
		settings=QSettings("DarunGrim LLC", "FlashHacker")

		self.ShowGraphs=True
		if settings.contains("General/ShowGraphs"):
			if settings.value("General/ShowGraphs")=='true':
				self.ShowGraphs=True
			else:
				self.ShowGraphs=False

		self.RABCDAsmPath=''
		if settings.contains("General/RABCDAsmPath"):
			self.RABCDAsmPath=settings.value("General/RABCDAsmPath")

		self.FirstConfigured=False
		if not settings.contains("General/FirstConfigured"):
			self.showConfiguration()
			self.FirstConfigured=True
		else:
			self.FirstConfigured=True

	def saveSettings(self):
		settings = QSettings("DarunGrim LLC", "FlashHacker")
		settings.setValue("General/ShowGraphs", self.ShowGraphs)
		settings.setValue("General/RABCDAsmPath", self.RABCDAsmPath)

		if self.FirstConfigured==True:
			settings.setValue("General/FirstConfigured", self.FirstConfigured)

	def closeEvent(self, event):
		self.saveSettings()
		self.saveUI()
		QMainWindow.closeEvent(self, event)

	def changeEvent(self,event):
		if event.type()==QEvent.WindowStateChange:
			if (self.windowState()&Qt.WindowMinimized)==0 and \
				 (self.windowState()&Qt.WindowMaximized)==0 and \
				 (self.windowState()&Qt.WindowFullScreen)==0 and \
				 (self.windowState()&Qt.WindowActive)==0:
					pass

	def resizeEvent(self,event):
		if not self.isMaximized():
			self.NonMaxGeometry=self.saveGeometry()

	def restoreUI(self):
		settings=QSettings("DarunGrim LLC", "FlashHacker")
		
		if settings.contains("geometry/non_max"):
			self.NonMaxGeometry=settings.value("geometry/non_max")
			self.restoreGeometry(self.NonMaxGeometry)
		else:
			self.resize(800,600)
			self.NonMaxGeometry=self.saveGeometry()
		
		if settings.contains("isMaximized"):
			if settings.value("isMaximized")=="true":
				self.setWindowState(self.windowState()|Qt.WindowMaximized)
		self.restoreState(settings.value("windowState"))

	def saveUI(self):
		settings=QSettings("DarunGrim LLC", "FlashHacker")
		if self.NonMaxGeometry!=None:
			settings.setValue("geometry/non_max", self.NonMaxGeometry)
		settings.setValue("isMaximized", self.isMaximized())
		settings.setValue("windowState", self.saveState())

if __name__=='__main__':
	import sys
	import time

	app=QApplication(sys.argv)
	#pixmap=QPixmap('DarunGrimSplash.png')
	#splash=QSplashScreen(pixmap)
	#splash.show()
	app.processEvents()
	window=MainWindow()

	if len(sys.argv)>1:
		window.showDir(sys.argv[1:])

	window.show()
	#splash.finish(window)
	sys.exit(app.exec_())
