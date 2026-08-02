clear all;close all;
PhysConsts;
home=cd;
%[PD0 q0]=LoadAstraParticles('../ASTRA/dlw.0166.001');
%[PD0 q0]=LoadAstraParticles('D:\PITZ\ASTRA_Simulation\Case_02\dlw.0419.001');
[PD0 q0]=LoadAstraParticles('../ECHO2D/round/particles.out');

PD=xpx2xxs(PD0);
PD(:,3)=PD(:,3)-PD(1,3);

q1=q0;

PD0=xxs2xpx(PD);

[s,I,ex,ey,se,gamma0,emitxn,emityn]=GlobalSliceAnalysis(PD,q1,1000,0.03,20,2)


subplot(2,1,1);
plot(s*1e6,ex,s*1e6,ey,s*1e6,I*1e-2,s*1e6,se*1e-3,'k:');
ylim([0 4]);
%plot(s*1e6,se*1e-3*6.5,'k:');
%smoothhist2D([PD(:,3)*1e6 PD(:,6)],5,[500, 500],0.0001);
subplot(2,1,2); plot(PD(:,3),PD(:,6),'.');
