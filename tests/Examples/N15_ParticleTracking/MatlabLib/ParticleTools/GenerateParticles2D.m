function PD=GenerateParticles2D(N,sigmaz,sigmaE,keyz,keyE)
% PD=GenerateParticles2D(N,sigmaz,sigmaE,keyz,keyE)
workdir='D:\MyTools\MatlabLib\ParticleTools\';
PhysConsts;
bound=5;
sqrt2=sqrt(2);
quant=(1+erf(-bound/sqrt2))/2;
exe_str = ['!' workdir 'loader 2 ',int2str(N)];
eval(exe_str); PD=load('P.txt');
if keyz=='g',  PD(:,1)=( PD(:,1)-0.5)*(1-2*quant)+0.5; PD(:,1)=sqrt2*erfinv(2*PD(:,1)-1); end;
if keyE=='g',  PD(:,2)=(PD(:,2)-0.5)*(1-2*quant)+0.5; PD(:,2)=sqrt2*erfinv(2*PD(:,2)-1);end;
[mzn mzsn mzzn  mzzsn mzszsn emitzn]=Moments(PD(:,1),PD(:,2));
PD(:,1)=(PD(:,1)-mzn)*sigmaz/sqrt(mzzn);PD(:,2)=(PD(:,2)-mzsn)*sigmaE/sqrt(mzszsn);
[mzn mzsn mzzn  mzzsn mzszsn emitzn]=Moments(PD(:,1),PD(:,2));
