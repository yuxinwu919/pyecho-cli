clear all; close all;
PhysConsts;
%%%%%%%%%%%%%%% INPUT %%%%%%%%%%%%%%%%%%%%%%
StepZ=0.0001; % in meters
BeamMonitorFile='../ECHO2D/round/BeamMomentsMonitor.txt';
dirAstra='D:\MyCalculations\PITZ\PITZ_April2017\ASTRA_Simulation\Case_03_SC'

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
be=load(BeamMonitorFile);htau=StepZ;
bax=load([dirAstra '\dlw.Xemit.001']);
za=bax(:,1);ta=bax(:,2)*1e-9*c; 
xa=bax(:,3)*1e-3;xrmsa=bax(:,4)*1e-3;
pxrmsa=bax(:,5)*1e-3;
emittxa=bax(:,6);xpxa=bax(:,7);
bay=load([dirAstra '\dlw.Yemit.001']);
ya=bay(:,3)*1e-3;yrmsa=bay(:,4)*1e-3;
pyrmsa=bay(:,5)*1e-3;
emittya=bay(:,6);ypya=bay(:,7);
baz=load([dirAstra '\dlw.Zemit.001']);
Ekina=baz(:,3);zrmsa=baz(:,4)*1e-3;
dErmsa=baz(:,5);
emittza=baz(:,6);zEa=baz(:,7);

K=(me*c^2)/e;
te=be(:,1)*htau+1.673;
xe=be(:,2);ye=be(:,3);ze=be(:,4);
pxe=be(:,5)*K;pye=be(:,6)*K;pze=be(:,7)*K;
x2e=be(:,8);y2e=be(:,9);z2e=be(:,10);
px2e=be(:,11)*K^2;py2e=be(:,12)*K^2;pz2e=be(:,13)*K^2;
xpxe=be(:,14)*K;ypye=be(:,15)*K;zpze=be(:,16)*K;
Ee=be(:,17)*E00; E2e=be(:,18)*E00^2;zEe=be(:,19)*E00;
xrmse=sqrt(x2e);pxrmse=sqrt(px2e);
emitt0=sqrt(x2e.*px2e-xpxe.^2);emittxe=emitt0/E00*1e6;
yrmse=sqrt(y2e);pyrmse=sqrt(py2e);
emitt0=sqrt(y2e.*py2e-ypye.^2);emittye=emitt0/E00*1e6;
zrmse=sqrt(z2e);pzrmse=sqrt(pz2e);
emitt0=sqrt(z2e.*pz2e-zpze.^2);emittze=emitt0/E00*1e6;
emitt0=sqrt(z2e.*E2e-zEe.^2);emittEe=emitt0;

 figure(1);
 subplot(2,2,1);
 plot(te,xe*1e3,ta,xa*1e3);
 xlabel('ct [m]'); ylabel('<x> [mm]');
 subplot(2,2,2);
 plot(te,xrmse*1e3,ta,xrmsa*1e3);
 xlabel('ct [m]'); ylabel('x_r_m_s [mm]');
 subplot(2,2,3);
 plot(te,emittxe,ta,emittxa);
 xlabel('ct [m]'); ylabel('emitt_x [um]');
 subplot(2,2,4);
 plot(te,pxrmse./pze*1e3,ta,pxrmsa*1e3);
 xlabel('ct [m]'); ylabel('px_r_m_s/<pz> [mrad]');

 figure(2);
 subplot(2,2,1);
 plot(te,ye*1e3,ta,ya*1e3);
 xlabel('ct [m]'); ylabel('<y> [mm]');
 subplot(2,2,2);
 plot(te,yrmse*1e3,ta,yrmsa*1e3);
 xlabel('ct [m]'); ylabel('y_r_m_s [mm]');
 subplot(2,2,3);
 plot(te,emittye,ta,emittya);
 xlabel('ct [m]'); ylabel('emitt_y [um]');
 subplot(2,2,4);
 plot(te,pyrmse./pze*1e3,ta,pyrmsa*1e3);
 xlabel('ct [m]'); ylabel('py_r_m_s/<pz> [mrad]');

figure(3);
subplot(2,2,1);
plot(te,Ee*1e-6,ta,Ekina);
xlabel('ct [m]'); ylabel('<E_k_i_n> [MeV]');
subplot(2,2,2);
plot(te,zrmse*1e3,ta,zrmsa*1e3);
xlabel('ct [m]'); ylabel('z_r_m_s [mm]');
subplot(2,2,3);
plot(te,emittEe,ta,emittza);
xlabel('ct [m]'); ylabel('emitt_z [m*eV]');
subplot(2,2,4);
plot(te,sqrt(E2e)*1e-3,ta,dErmsa);
xlabel('ct [m]'); ylabel('E_k_i_n_,_r_m_s [keV]');


