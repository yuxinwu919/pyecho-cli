function B=s_to_cur(A,sigma,q0,v)
% A - s-coordinates of particles
% sigma -smoothing parameter
% q0 -bunch charge
% v mean velocity
    Nsigma=3;
    a=min(A)-Nsigma*sigma;    b=max(A)+Nsigma*sigma;
    s=0.25*sigma;
    N=ceil((b-a)/s); s=(b-a)/N;
    B=zeros(N+1,2); C=zeros(N+1,1);
    B(:,1)=[0:s:(N+0.5)*s]+a; N=length(B(:,1));
    cA=(A-a)/s;
    I=floor(cA);
    xiA=1+I-cA;
    for k=1:size(A),
        i=I(k); 
        if i>N-1, i=N-1; end;
        C(i+1)=C(i+1)+xiA(k);
        C(i+2)=C(i+2)+(1-xiA(k));
    end;
    K=floor(Nsigma*sigma/s+0.5);
    G=exp(-0.5*([-K:K]*s/sigma).^2); 
    G=G/sum(G);
    B(:,2)=convmode(C,G,1);
    koef=q0*v/(s*sum(B(:,2)));
    B(:,2)=koef*B(:,2);
 