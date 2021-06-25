import logging
import os
from pathlib import Path

import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

#
# ProcrustesRegistrationModule
#

class ProcrustesRegistrationModule(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Procrustes Registration"
    self.parent.categories = ["Shape Analysis"]
    self.parent.dependencies = []
    self.parent.contributors = ["Ye Han (Kitware, Inc.)"]
    self.parent.helpText = (
      "Procrustes registration using vtkProcrustesAlignmentFilter."
    )
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = (
      "This file was originally developed by Jean-Christophe Fillion-Robin, "
      "Kitware Inc., Andras Lasso, PerkLab, and Steve Pieper, Isomics, Inc. "
      "and was partially funded by NIH grant 3P41RR013218-12S1."
    )

#
# ProcrustesRegistrationModuleWidget
#

class ProcrustesRegistrationModuleWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.logic = None

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ProcrustesRegistrationModule.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    self.ui.tableWidget_VTKFiles.setColumnCount(2)
    self.ui.tableWidget_VTKFiles.setHorizontalHeaderLabels([' VTK files ', ' Set as reference '])
    self.ui.tableWidget_VTKFiles.setColumnWidth(0, 300)
    self.ui.tableWidget_VTKFiles.setColumnWidth(1, 200)
    horizontalHeader = self.ui.tableWidget_VTKFiles.horizontalHeader()
    horizontalHeader.setStretchLastSection(True)
    self.ui.tableWidget_VTKFiles.verticalHeader().setVisible(True)
    self.referenceButtonGroup = qt.QButtonGroup()
    self.referenceButtonGroup.setExclusive(True)

    self.logic = ProcrustesRegistrationModuleLogic()
    self.ui.ApplyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.LoadButton.connect('clicked(bool)', self.onLoadButton)
    self.ui.SaveButton.connect('clicked(bool)', self.onSaveButton)

  def cleanup(self):
    pass

  def onLoadButton(self):
    self.logic.loadData(
      Path(self.ui.InputDirectory.directory),
      self.ui.tableWidget_VTKFiles,
      self.referenceButtonGroup
    )

  def onApplyButton(self):
    self.logic.run(
      Path(self.ui.InputDirectory.directory),
      self.ui.tableWidget_VTKFiles,
      self.ui.ScalingCheckBox
    )

  def onSaveButton(self):
    self.logic.saveData(
      Path(self.ui.OutputDirectory.directory),
           self.ui.tableWidget_VTKFiles,
           self.ui.TransformCheckBox
    )

#
# ProcrustesRegistrationModuleLogic
#

class ProcrustesRegistrationModuleLogic(ScriptedLoadableModuleLogic):
  def run(self, input: Path, table, scaling):
    logging.info('Processing started')

    # Get reference id from widget
    for row in range(table.rowCount):
      if table.cellWidget(row, 1).layout().itemAt(0).widget().isChecked() == True:
        self.referenceId = row

    # Read inputs as multi-block polydata
    group = vtk.vtkMultiBlockDataGroupFilter()
    filename = table.cellWidget(self.referenceId, 0).text
    filepath = str(input) + '/' + filename
    reader = vtk.vtkPolyDataReader()
    reader.SetFileName(filepath)
    reader.Update()
    group.AddInputDataObject(reader.GetOutput())

    for row in range(table.rowCount):
      if row != self.referenceId:
        filename = table.cellWidget(row, 0).text
        filepath = str(input) + '/' + filename
        reader = vtk.vtkPolyDataReader()
        reader.SetFileName(filepath)
        reader.Update()
        group.AddInputDataObject(reader.GetOutput())
    group.Update()
    self.inputPDs = group.GetOutput()

    # Procrustes alignment
    procrustes = vtk.vtkProcrustesAlignmentFilter()
    procrustes.SetInputConnection(group.GetOutputPort())
    if scaling.isChecked():
      procrustes.GetLandmarkTransform().SetModeToSimilarity()
    else:
      procrustes.GetLandmarkTransform().SetModeToRigidBody()
    procrustes.Update()

    # Compute transforms and create mrml nodes
    scene = slicer.mrmlScene
    self.outputPDs = procrustes.GetOutput()
    self.transforms = list()
    for row in range(table.rowCount):
      if row < self.referenceId:
        blockId = row + 1
      elif row > self.referenceId:
        blockId = row
      else:
        blockId = 0
      inputPD = self.inputPDs.GetBlock(blockId)
      outputPD = self.outputPDs.GetBlock(blockId)

      # Re-compute actual transform
      landmarkTransform = vtk.vtkLandmarkTransform()
      landmarkTransform.SetSourceLandmarks(inputPD.GetPoints())
      landmarkTransform.SetTargetLandmarks(outputPD.GetPoints())
      landmarkTransform.Update()

      # Add nodes to scene
      modelNode = slicer.vtkMRMLModelNode()
      modelNode.SetScene(scene)
      modelNode.SetName(scene.GenerateUniqueName(table.cellWidget(row, 0).text))
      modelNode.SetAndObservePolyData(inputPD)

      transformNode = slicer.vtkMRMLLinearTransformNode()
      transformNode.SetName(modelNode.GetName() + "_transform")
      scene.AddNode(transformNode)
      transformNode.SetMatrixTransformToParent(landmarkTransform.GetMatrix())
      modelNode.SetAndObserveTransformNodeID(transformNode.GetID())
      self.transforms.append(transformNode)

      displayNode = slicer.vtkMRMLModelDisplayNode()
      displayNode.SetColor(0, 1, 1)  # cyan
      displayNode.SetBackfaceCulling(0)
      displayNode.SetScene(scene)
      scene.AddNode(displayNode)
      modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
      scene.AddNode(modelNode)

    # Show mean surface
    meanPoints = procrustes.GetMeanPoints()
    self.meanSurface = vtk.vtkPolyData()
    self.meanSurface.DeepCopy(self.outputPDs.GetBlock(0))
    self.meanSurface.SetPoints(meanPoints)

    meanModelNode = slicer.vtkMRMLModelNode()
    meanModelNode.SetScene(scene)
    meanModelNode.SetName(scene.GenerateUniqueName("mean_surface"))
    meanModelNode.SetAndObservePolyData(self.meanSurface)

    meanDisplayNode = slicer.vtkMRMLModelDisplayNode()
    meanDisplayNode.SetColor(1, 0, 0)  # red
    meanDisplayNode.SetBackfaceCulling(0)
    meanDisplayNode.SetScene(scene)
    scene.AddNode(meanDisplayNode)
    meanModelNode.SetAndObserveDisplayNodeID(meanDisplayNode.GetID())
    scene.AddNode(meanModelNode)

    logging.info('Processing completed')
    return True

  def loadData(self, input: Path, table, methodButtonGroup):
    logging.info('Load data')

    if not input.is_dir():
      raise ValueError('data directory is not valid.')

    # Fill a table with vtk filenames in input directory
    valueList = list()
    for file in os.listdir(input):
        if file.endswith(".vtk"):
            filepath = str(input) + '/' + file
            print(filepath)
            valueList.append(filepath)

    table.setRowCount(len(valueList))
    table.setColumnCount(2)
    row = 0
    for vtkFile in valueList:
        # Column 0:
        filename = os.path.basename(vtkFile)
        labelVTKFile = qt.QLabel(filename)
        labelVTKFile.setAlignment(0x84)
        table.setCellWidget(row, 0, labelVTKFile)

        # Column 1:
        widget = qt.QWidget()
        layout = qt.QHBoxLayout(widget)
        checkBox = qt.QCheckBox()
        layout.addWidget(checkBox)
        layout.setAlignment(0x84)
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        table.setCellWidget(row, 1, widget)
        methodButtonGroup.addButton(checkBox)

        row = row + 1

  def saveData(self, output: Path, table, transform):
    logging.info('Save data')

    if not output.is_dir():
      raise ValueError('output directory is not valid.')

    for row in range(table.rowCount):
      if row < self.referenceId:
        blockId = row + 1
      elif row > self.referenceId:
        blockId = row
      else:
        blockId = 0

      filepath = str(output) + '/' + os.path.splitext(table.cellWidget(row, 0).text)[0] + '_aligned.vtk'
      writer = vtk.vtkPolyDataWriter()
      writer.SetFileName(filepath)
      writer.SetInputDataObject(self.outputPDs.GetBlock(blockId))
      writer.Write()

      # Save transforms
      if transform.isChecked():
        storage = slicer.vtkMRMLTransformStorageNode()
        storage.SetFileName(str(output) + '/' + os.path.splitext(table.cellWidget(row, 0).text)[0] + ".h5")
        storage.WriteData(self.transforms[row])

class ProcrustesRegistrationModuleTest(ScriptedLoadableModuleTest):

  def setUp(self):
    pass

  def runTest(self):
    self.setUp()
    self.test_ProcrustesRegistrationModule1()

  def test_ProcrustesRegistrationModule1(self):
    pass
