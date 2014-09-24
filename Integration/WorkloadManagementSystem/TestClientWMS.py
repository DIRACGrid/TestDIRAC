""" This is a test of using WMSClient and several other functions in WMS

    In order to run this test we need the following DBs installed:
    - JobDB
    - JobLoggingDB
    - TaskQueueDB
    - SandboxMetadataDB
    - PilotAgentsDB

    And the following services should also be on:
    - OptimizationMind
    - JobManager
    - SandboxStore
    - JobMonitoring
    - JobStateUpdate
    - WMSAdministrator
    
    A user proxy is also needed to submit,
    and the Framework/ProxyManager need to be running with a such user proxy already uploaded.

    Due to the nature of the DIRAC WMS, only a full chain test makes sense,
    and this also means that this test is not easy to set up.
"""

import unittest, datetime
import os, tempfile
# from mock import Mock

from DIRAC.Core.Base.Script import parseCommandLine
parseCommandLine()

from DIRAC.Interfaces.API.Job import Job
from DIRAC.Core.DISET.RPCClient import RPCClient
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import JobMonitoringClient
from DIRAC.WorkloadManagementSystem.Agent.JobCleaningAgent import JobCleaningAgent
from DIRAC.WorkloadManagementSystem.DB.PilotAgentsDB import PilotAgentsDB

from DIRAC import gLogger

def helloWorldJob():
  job = Job()
  job.setName( "helloWorld" )
  job.setInputSandbox( '../../Integration/WorkloadManagementSystem/exe-script.py' )
  job.setExecutable( "exe-script.py", "", "helloWorld.log" )
  return job

def createFile( job ):
  tmpdir = tempfile.mkdtemp()
  jobDescription = tmpdir + '/jobDescription.xml'
  fd = os.open( jobDescription, os.O_RDWR | os.O_CREAT )
  os.write( fd, job._toXML() )
  os.close( fd )
  return jobDescription




class TestWMSTestCase( unittest.TestCase ):

  def setUp( self ):
    self.maxDiff = None

    gLogger.setLevel( 'VERBOSE' )

  def tearDown( self ):
    """ use the JobCleaningAgent method to remove the jobs in status 'deleted' and 'Killed'
    """
    jca = JobCleaningAgent( 'WorkloadManagement/JobCleaningAgent',
                            'WorkloadManagement/JobCleaningAgent' )
    jca.initialize()
    res = jca.removeJobsByStatus( { 'Status' : ['Killed', 'Deleted'] } )
    self.assert_( res['OK'] )

class WMSChain( TestWMSTestCase ):

  def test_FullChain( self ):
    """ This test will

        - call all the WMSClient methods
          that will end up calling all the JobManager service methods
        - use the JobMonitoring to verify few properties
        - call the JobCleaningAgent to eliminate job entries from the DBs
    """
    wmsClient = WMSClient()
    jobMonitor = JobMonitoringClient()
    jobStateUpdate = RPCClient( 'WorkloadManagement/JobStateUpdate' )

    # create the job
    job = helloWorldJob()
    jobDescription = createFile( job )

    # submit the job
    res = wmsClient.submitJob( job._toJDL( xmlFile = jobDescription ) )
    self.assert_( res['OK'] )
    self.assertEqual( type( res['Value'] ), int )
    self.assertEqual( res['Value'], res['JobID'] )
    jobID = res['JobID']

    # updating the status
    jobStateUpdate.setJobStatus( jobID, 'Running', 'Executing Minchiapp', 'source' )

    # reset the job
    res = wmsClient.resetJob( jobID )
    self.assertFalse( res['OK'] )  # only admins can reset

    # reschedule the job
    res = wmsClient.rescheduleJob( jobID )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobStatus( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Received' )

    # updating the status again
    jobStateUpdate.setJobStatus( jobID, 'Matched', 'matching', 'source' )

    # kill the job
    res = wmsClient.killJob( jobID )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobStatus( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Killed' )

    # updating the status aaaagain
    jobStateUpdate.setJobStatus( jobID, 'Done', 'matching', 'source' )

    # kill the job
    res = wmsClient.killJob( jobID )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobStatus( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Done' )  # this time it won't kill... it's done!

    # delete the job - this will just set its status to "deleted"
    res = wmsClient.deleteJob( jobID )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobStatus( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Deleted' )


class JobMonitoring( TestWMSTestCase ):

  def test_JobStateUpdateAndJobMonitoring( self ):
    """ Verifying all JobStateUpdate and JobMonitoring functions
    """
    wmsClient = WMSClient()
    jobMonitor = JobMonitoringClient()
    jobStateUpdate = RPCClient( 'WorkloadManagement/JobStateUpdate' )

    # create a job and check stuff
    job = helloWorldJob()
    jobDescription = createFile( job )

    # submitting the job. Checking few stuff
    res = wmsClient.submitJob( job._toJDL( xmlFile = jobDescription ) )
    self.assert_( res['OK'] )
    jobID = res['JobID']
    res = jobMonitor.getJobJDL( jobID )
    self.assert_( res['OK'] )

    # Adding stuff
    res = jobStateUpdate.setJobStatus( jobID, 'Matched', 'matching', 'source' )
    self.assert_( res['OK'] )
    res = jobStateUpdate.setJobParameters( jobID, [( 'par1', 'par1Value' ), ( 'par2', 'par2Value' )] )
    self.assert_( res['OK'] )
    res = jobStateUpdate.setJobApplicationStatus( jobID, 'Minchiapp status', 'source' )
    self.assert_( res['OK'] )
#     res = jobStateUpdate.setJobFlag()
#     self.assert_( res['OK'] )
#     res = jobStateUpdate.unsetJobFlag()
#     self.assert_( res['OK'] )
    res = jobStateUpdate.setJobSite( jobID, 'Site' )
    self.assert_( res['OK'] )
    res = jobMonitor.traceJobParameter( 'Site', 1, 'Status' )
    self.assert_( res['OK'] )

    # now checking few things
    res = jobMonitor.getJobStatus( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Running' )
    res = jobMonitor.getJobParameter( jobID, 'par1' )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], {'par1': 'par1Value'} )
    res = jobMonitor.getJobParameters( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], {'par1': 'par1Value', 'par2': 'par2Value'} )
    res = jobMonitor.getJobAttribute( jobID, 'Site' )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], 'Site' )
    res = jobMonitor.getJobAttributes( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['ApplicationStatus'], 'Minchiapp status' )
    self.assertEqual( res['Value']['JobName'], 'helloWorld' )
    res = jobMonitor.getJobSummary( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['ApplicationStatus'], 'Minchiapp status' )
    self.assertEqual( res['Value']['Status'], 'Running' )
    res = jobMonitor.getJobHeartBeatData( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], [] )
    res = jobMonitor.getInputData( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], [] )
    res = jobMonitor.getJobPrimarySummary( jobID )
    self.assert_( res['OK'] )
    res = jobMonitor.getAtticJobParameters( jobID )
    self.assert_( res['OK'] )
    res = jobStateUpdate.setJobsStatus( [jobID], 'Done', 'MinorStatus', 'Unknown' )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobSummary( jobID )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['Status'], 'Done' )
    self.assertEqual( res['Value']['MinorStatus'], 'MinorStatus' )
    self.assertEqual( res['Value']['ApplicationStatus'], 'Minchiapp status' )
    res = jobStateUpdate.sendHeartBeat( jobID, {'bih':'bih'}, {'boh':'boh'} )
    self.assert_( res['OK'] )


    # delete the job - this will just set its status to "deleted"
    wmsClient.deleteJob( jobID )


#     # Adding a platform
#     self.getDIRACPlatformMock.return_value = {'OK': False}
#
#     job = helloWorldJob()
#     job.setPlatform( "x86_64-slc6" )
#
#     jobDescription = createFile( job )
#
#     job.setCPUTime( 17800 )
#     job.setBannedSites( ['LCG.CERN.ch', 'LCG.CNAF.it', 'LCG.GRIDKA.de', 'LCG.IN2P3.fr',
#                          'LCG.NIKHEF.nl', 'LCG.PIC.es', 'LCG.RAL.uk', 'LCG.SARA.nl'] )
#     res = WMSClient().submitJob( job._toJDL( xmlFile = jobDescription ) )
#     self.assert_( res['OK'] )
#     self.assertEqual( type( res['Value'] ), int )



  def test_JobStateUpdateAndJobMonitoringMultuple( self ):
    """ # Now, let's submit some jobs. Different sites, types, inputs
    """
    wmsClient = WMSClient()
    jobMonitor = JobMonitoringClient()
    jobStateUpdate = RPCClient( 'WorkloadManagement/JobStateUpdate' )

    jobIDs = []
    dests = ['DIRAC.site1.org', 'DIRAC.site2.org']
    lfnss = [['/a/1.txt', '/a/2.txt'], ['/a/1.txt', '/a/3.txt', '/a/4.txt'], []]
    types = ['User', 'Test']
    for dest in dests:
      for lfns in lfnss:
        for jobType in types:
          job = helloWorldJob()
          job.setDestination( dest )
          job.setInputData( lfns )
          job.setType( jobType )
          jobDescription = createFile( job )
          res = wmsClient.submitJob( job._toJDL( xmlFile = jobDescription ) )
          self.assert_( res['OK'] )
          jobID = res['JobID']
          jobIDs.append( jobID )

    res = jobMonitor.getSites()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( dests ) )
    res = jobMonitor.getJobTypes()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( types ) )
    res = jobMonitor.getApplicationStates()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( ['Unknown'] ) )

    res = jobMonitor.getOwners()
    self.assert_( res['OK'] )
    res = jobMonitor.getOwnerGroup()
    self.assert_( res['OK'] )
    res = jobMonitor.getProductionIds()
    self.assert_( res['OK'] )
    res = jobMonitor.getJobGroups()
    self.assert_( res['OK'] )
    res = jobMonitor.getStates()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( ['Received'] ) )
    res = jobMonitor.getMinorStates()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( ['Job accepted'] ) )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobs()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), [str( x ) for x in sorted( jobIDs )] )
#     res = jobMonitor.getCounters(attrList)
#     self.assert_( res['OK'] )
    res = jobMonitor.getCurrentJobCounters()
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], {'Received': long( len( dests ) * len( lfnss ) * len( types ) )} )
    res = jobMonitor.getJobsSummary( jobIDs )
    self.assert_( res['OK'] )
    res = jobMonitor.getJobPageSummaryWeb( {}, [], 0, 100 )
    self.assert_( res['OK'] )

    res = jobStateUpdate.setJobStatusBulk( jobID, {str( datetime.datetime.utcnow() ):{'Status': 'Running',
                                                                                      'MinorStatus': 'MinorStatus',
                                                                                      'ApplicationStatus': 'ApplicationStatus',
                                                                                      'Source': 'Unknown'}} )
    self.assert_( res['OK'] )
    res = jobStateUpdate.setJobsParameter( {jobID:['Status', 'Running']} )
    self.assert_( res['OK'] )

    # delete the jobs - this will just set its status to "deleted"
    wmsClient.deleteJob( jobIDs )


#   def test_submitFail( self ):
#
#     # Adding a platform that should not exist
#     job = helloWorldJob()
#     job.setPlatform( "notExistingPlatform" )
#     jobDescription = createFile( job )
#
#     res = WMSClient().submitJob( job._toJDL( xmlFile = jobDescription ) )
#     self.assert_( res['OK'] )
#
#     WMSClient().deleteJob( res['Value'] )


class WMSAdministrator( TestWMSTestCase ):
  """ testing WMSAdmin - for JobDB and PilotsDB
  """
  
  def test_JobDBWMSAdmin(self):
  
    wmsAdministrator = RPCClient( 'WorkloadManagement/WMSAdministrator' )

    sitesList = ['My.Site.org', 'Your.Site.org']
    res = wmsAdministrator.setSiteMask( sitesList )
    self.assert_( res['OK'] )
    res = wmsAdministrator.getSiteMask()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( sitesList ) )
    res = wmsAdministrator.banSite( 'My.Site.org', 'This is a comment' )
    self.assert_( res['OK'] )
    res = wmsAdministrator.getSiteMask()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), ['Your.Site.org'] )
    res = wmsAdministrator.allowSite( 'My.Site.org', 'This is a comment' )
    self.assert_( res['OK'] )
    res = wmsAdministrator.getSiteMask()
    self.assert_( res['OK'] )
    self.assertEqual( sorted( res['Value'] ), sorted( sitesList ) )

    res = wmsAdministrator.getSiteMaskLogging( sitesList )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['My.Site.org'][0][3], 'No comment' )
    res = wmsAdministrator.getSiteMaskSummary()
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['My.Site.org'], 'Active' )

    res = wmsAdministrator.getUserSummaryWeb( {}, [], 0, 100 )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['TotalRecords'], 0 )
    res = wmsAdministrator.getSiteSummaryWeb( {}, [], 0, 100 )
    self.assert_( res['OK'] )
    self.assertEqual( res['Value']['TotalRecords'], 0 )
    res = wmsAdministrator.getSiteSummarySelectors()
    self.assert_( res['OK'] )

    res = wmsAdministrator.clearMask()
    self.assert_( res['OK'] )
    res = wmsAdministrator.getSiteMask()
    self.assert_( res['OK'] )
    self.assertEqual( res['Value'], [] )

  def test_PilotsDB( self ):

    wmsAdministrator = RPCClient( 'WorkloadManagement/WMSAdministrator' )
    pilotAgentDB = PilotAgentsDB()


#     res = wmsAdministrator.addPilotTQReference()
#     self.assert_( res['OK'] )
#
#     res = wmsAdministrator.getCurrentPilotCounters()
#     self.assert_( res['OK'] )
#     self.assertEqual( res['Value'], {} )

#     res = wmsAdministrator.getPilotOutput()
# self.assert_( res['OK'] )
#     res = wmsAdministrator.getPilotInfo()
# self.assert_( res['OK'] )
#     res = wmsAdministrator.selectPilots()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.storePilotOutput()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilotLoggingInfo()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getJobPilotOutput()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilotSummary()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilotMonitorWeb()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilotMonitorSelectors()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilotSummaryWeb()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.getPilots()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.killPilot()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.setJobForPilot()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.setPilotBenchmark()
# self.assert_( res['OK'] )
# #     res = wmsAdministrator.setAccountingFlag()
# self.assert_( res['OK'] )
#
#     setPilotStatus
#     countPilots
#     getCounters
#     # getPilotStatistics

if __name__ == '__main__':
  suite = unittest.defaultTestLoader.loadTestsFromTestCase( TestWMSTestCase )
#   suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( WMSChain ) )
  suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( JobMonitoring ) )
#   suite.addTest( unittest.defaultTestLoader.loadTestsFromTestCase( WMSAdministrator ) )
  testResult = unittest.TextTestRunner( verbosity = 2 ).run( suite )
