clear all;close all;
PhysConsts;
%%%%%%%%%%%%%% INPUT %%%%%%%%%%%%%%%%%%%%%%%%
File1='../ASTRA/dlw.0166.001';
File2='../ECHO2D/round/particles.out';


home=cd;
[PD1 q1]=LoadAstraParticles(File1);
[PD0 q0]=LoadAstraParticles(File2);
PD0(:,3)=PD0(:,3)-PD0(1,3);
PD1(:,3)=PD1(:,3)-PD1(1,3);
N=length(PD1(:,3));
%N=10;
i1=3; i2=6;
subplot(2,1,1);
plot(PD0(:,i1)*1e3,PD0(:,i2)*1e-6,'g.',PD1(:,i1)*1e3,PD1(:,i2)*1e-6,'b.')
xlabel('z [mm]'); ylabel('p_z [MeV]');
%plot([1:N],PD0(1:N,i2),'k.',[1:N],PD1(1:N,i2),'b.')
subplot(2,1,2);
plot(PD1(:,i1)*1e3,PD1(:,i2)*1e-6,'b.',PD0(:,i1)*1e3,PD0(:,i2)*1e-6,'g.')
xlabel('z [mm]'); ylabel('p_z [MeV]');
%plot([1:N],PD1(1:N,i2),'b.',[1:N],PD0(1:N,i2),'k.')

 K=e/(me*c^2);
 pp=PD0(2,4:6)*K;
 gamma=sqrt(1+pp(1)*pp(1)+pp(2)*pp(2)+pp(3)*pp(3))
 x2=PD0(2,1)+pp(1)/gamma*0.5
 PD1(2,1)

return;


PD=xpx2xxs(PD0);
PD(:,3)=PD(:,3)-PD(1,3);

q1=q0;

PD0=xxs2xpx(PD);

[s,I,ex,ey,se,gamma0,emitxn,emityn]=GlobalSliceAnalysis(PD,q1,1000,0.1,20,2)



plot(s*1e6,ex,s*1e6,ey,s*1e6,I*1e-2,s*1e6,se*1e-3,'k:');
%ylim([0 4]);
%plot(s*1e6,se*1e-3*6.5,'k:');
%smoothhist2D([PD(:,3)*1e6 PD(:,6)],5,[500, 500],0.0001);
%subplot(1,1,1); plot(PD(:,3),PD(:,6),'.');
